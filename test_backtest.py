"""Synthetic checks for data ingestion, accounting, metrics, and causal strategy rules."""
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backtest import (
    Bar,
    CostModel,
    QuantityConstraints,
    _trade_distribution,
    SignalDecision,
    compute_window_metrics,
    load_binance_quantity_constraints,
    load_binance_vision_klines,
    make_exp_strategy_policy,
    parse_binance_kline_row,
    run_backtest,
    run_buy_and_hold,
    _trade_duration_summary,
)


ZERO_COSTS = CostModel(0, 0, 0)
BTC_LIKE = QuantityConstraints(0.0001, 0.0001, 10, 5)


def make_bars(closes, opens=None):
    opens = list(closes if opens is None else opens)
    first = date(2020, 1, 1)
    return [
        Bar((first + timedelta(days=i)).isoformat(), op, max(op, close) + 1, min(op, close) - 1, close)
        for i, (op, close) in enumerate(zip(opens, closes))
    ]


def make_kline_row(
    session, *, unit, interval="1d", hour=0, open_price="100", high="102", low="99", close="101",
    quote_volume="1250.0",
):
    opened = datetime.combine(session, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=hour)
    open_ts = int(opened.timestamp()) * unit
    interval_seconds = 86_400 if interval == "1d" else 14_400
    close_ts = open_ts + interval_seconds * unit - 1
    return [
        str(open_ts), open_price, high, low, close, "12.5", str(close_ts),
        quote_volume, "42", "6.0", "600.0", "0",
    ]


def make_h4_bars(closes, *, opens=None, highs=None, lows=None, quote_volumes=None, first=datetime(2020, 1, 1, tzinfo=timezone.utc)):
    opens = list(closes if opens is None else opens)
    highs = list(highs) if highs is not None else [max(op, close) + 1 for op, close in zip(opens, closes)]
    lows = list(lows) if lows is not None else [min(op, close) - 1 for op, close in zip(opens, closes)]
    quote_volumes = list(quote_volumes if quote_volumes is not None else [100.0] * len(closes))
    bars = []
    for i, (op, high, low, close, volume) in enumerate(zip(opens, highs, lows, closes, quote_volumes)):
        opened = first + timedelta(hours=4 * i)
        closed = opened + timedelta(hours=4) - timedelta(milliseconds=1)
        bars.append(Bar(
            opened.isoformat(timespec="seconds").replace("+00:00", "Z"),
            float(op), float(high), float(low), float(close), float(volume),
            closed.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        ))
    return bars


def write_fixture_dataset(root: Path, rows, *, symbol="BTCUSDT", interval="1d", archive_month="2025-01"):
    root.mkdir(parents=True, exist_ok=True)
    name = f"{symbol}-{interval}-{archive_month}.zip"
    csv_name = f"{symbol}-{interval}-{archive_month}.csv"
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    zip_path = root / name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(csv_name, buffer.getvalue())
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (root / f"{name}.CHECKSUM").write_text(f"{digest}  {name}\n", encoding="utf-8")
    (root / "download_manifest.json").write_text(json.dumps({
        "verified_archive_count": 1,
        "expected_archive_count": 1,
        "archives": [{"file": name, "sha256": digest}],
    }), encoding="utf-8")


class BacktestTests(unittest.TestCase):
    def test_entry_uses_next_open_after_closed_bar_signal(self):
        closes = [100.0] * 100 + [101.0, 102.0, 103.0, 104.0]
        opens = closes.copy()
        opens[101] = 200.0
        bars = make_bars(closes, opens)
        result = run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS)
        buy = next(fill for fill in result.fills if fill.side == "BUY")
        self.assertEqual(buy.signal_session, bars[100].session)
        self.assertEqual(buy.fill_session, bars[101].session)
        self.assertEqual(buy.reference_price, 200.0)
        self.assertEqual(result.equity_curve[100].quantity, 0)
        self.assertGreater(result.equity_curve[101].quantity, 0)

    def test_exit_cross_uses_next_open(self):
        closes = [100.0] * 100 + list(map(float, range(101, 131))) + list(map(float, range(130, 79, -1)))
        bars = make_bars(closes, [close + 0.5 for close in closes])
        result = run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS)
        sell = next(fill for fill in result.fills if fill.side == "SELL" and fill.reason == "sma_cross")
        signal_index = next(i for i, bar in enumerate(bars) if bar.session == sell.signal_session)
        self.assertEqual(sell.fill_session, bars[signal_index + 1].session)
        self.assertEqual(sell.reference_price, bars[signal_index + 1].open)

    def test_fractional_sizing_floors_to_step(self):
        closes = [100.0] * 100 + [101.0, 102.0, 103.0, 104.0]
        opens = closes.copy()
        opens[101] = 300.0
        result = run_backtest(make_bars(closes, opens), initial_capital=1_000, costs=ZERO_COSTS, constraints=BTC_LIKE)
        buy = next(fill for fill in result.fills if fill.side == "BUY")
        self.assertAlmostEqual(buy.quantity, 3.3333, places=8)
        self.assertAlmostEqual(buy.quantity / 0.0001, round(buy.quantity / 0.0001))
        self.assertGreaterEqual(result.equity_curve[101].cash, 0)

    def test_minimum_notional_rejects_too_small_order(self):
        bars = make_bars([100.0] * 100 + [101.0, 102.0])
        rules = QuantityConstraints(0.0001, 0.0001, 10, 5)
        result = run_backtest(bars, initial_capital=4, costs=ZERO_COSTS, constraints=rules)
        self.assertEqual(result.fills, ())
        self.assertEqual(result.rejected_orders[0].detail, "below_minimum_notional")

    def test_maximum_quantity_is_respected(self):
        closes = [100.0] * 100 + [101.0, 102.0, 103.0]
        opens = closes.copy()
        opens[101] = 100.0
        rules = QuantityConstraints(0.01, 0.01, 0.5, 1)
        result = run_backtest(make_bars(closes, opens), initial_capital=1_000, costs=ZERO_COSTS, constraints=rules)
        self.assertEqual(next(f.quantity for f in result.fills if f.side == "BUY"), 0.5)

    def test_costs_and_trade_pnl_reconcile(self):
        closes = [100.0] * 100 + [101.0, 102.0, 103.0, 104.0]
        opens = closes.copy()
        opens[101] = 200.0
        costs = CostModel(10, 2, 3)
        result = run_backtest(make_bars(closes, opens), initial_capital=100_000, costs=costs)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertAlmostEqual(result.fills[0].fill_price, result.fills[0].reference_price * 1.0004)
        self.assertAlmostEqual(result.fills[-1].fill_price, result.fills[-1].reference_price * 0.9996)
        self.assertAlmostEqual(trade.net_pnl, trade.gross_pnl - trade.total_costs, places=7)
        self.assertAlmostEqual(result.final_capital, result.initial_capital + trade.net_pnl, places=7)
        self.assertAlmostEqual(result.equity_curve[-1].equity, result.final_capital, places=7)

    def test_open_position_costs_are_counted_when_terminal_sale_rejected(self):
        closes = [100.0] * 100 + [101.0, 102.0]
        opens = closes.copy()
        opens[101] = 300.0
        rules = QuantityConstraints(0.0001, 0.0001, 10, 500)
        result = run_backtest(
            make_bars(closes, opens), initial_capital=1_000,
            costs=CostModel(10, 2, 3), constraints=rules,
        )
        self.assertTrue(result.fills)
        self.assertGreater(result.total_costs, 0)
        self.assertEqual(len(result.trades), 0)
        self.assertGreater(result.equity_curve[-1].quantity, 0)

    def test_rejected_final_sale_remains_marked_to_market(self):
        result = run_buy_and_hold(
            make_bars([100.0, 10.0]), initial_capital=1_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 10, 200),
        )
        self.assertEqual(len(result.fills), 1)
        self.assertGreater(result.equity_curve[-1].quantity, 0)
        self.assertEqual(result.final_capital, result.equity_curve[-1].equity)
        self.assertEqual(result.rejected_orders[-1].reason, "end_of_test")

    def test_buy_and_hold_starts_at_first_open_and_reconciles(self):
        bars = make_bars([100.0, 110.0, 120.0])
        result = run_buy_and_hold(
            bars, initial_capital=1_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 100, 0),
        )
        self.assertEqual(result.fills[0].fill_session, bars[0].session)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertEqual(result.fills[-1].side, "SELL")
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.final_capital, 1_200)

    def test_window_metrics_use_close_equity_and_exit_date(self):
        bars = make_bars([100.0, 105.0, 110.0])
        result = run_buy_and_hold(
            bars, initial_capital=1_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 100, 0),
        )
        metrics = compute_window_metrics(
            result, start_session=date(2020, 1, 1), end_session=date(2020, 1, 3)
        )
        self.assertAlmostEqual(metrics.net_return_pct, 10)
        self.assertEqual(metrics.trade_count, 1)
        self.assertAlmostEqual(metrics.exposure_pct, 200 / 3)
        self.assertEqual(metrics.total_costs_usdt, 0)

    def test_flat_series_preserves_capital(self):
        result = run_backtest(make_bars([100.0] * 120), initial_capital=10_000, costs=ZERO_COSTS)
        self.assertEqual(result.trades, ())
        self.assertEqual(result.fills, ())
        self.assertEqual(result.final_capital, 10_000)
        self.assertEqual(result.total_costs, 0)

    def test_insufficient_cash_is_recorded(self):
        bars = make_bars([100.0] * 100 + [101.0, 102.0])
        result = run_backtest(bars, initial_capital=0.5, costs=ZERO_COSTS)
        self.assertEqual(result.fills, ())
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(result.rejected_orders[0].detail, "insufficient_cash_for_minimum_quantity")

    def test_runs_are_reproducible(self):
        bars = make_bars([100.0] * 100 + [101.0, 102.0, 103.0, 104.0])
        self.assertEqual(
            run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS),
            run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS),
        )

    def test_invalid_and_missing_ohlc_are_rejected(self):
        valid = make_bars([100.0, 101.0])
        missing = [valid[0], Bar(valid[1].session, float("nan"), 102.0, 100.0, 101.0)]
        duplicate = [valid[0], Bar(valid[0].session, 101.0, 102.0, 100.0, 101.0)]
        with self.assertRaisesRegex(ValueError, "OHLC"):
            run_backtest(missing, initial_capital=1_000, costs=ZERO_COSTS)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            run_backtest(duplicate, initial_capital=1_000, costs=ZERO_COSTS)

    def test_inconsistent_ohlc_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            run_backtest([Bar("2020-01-01", 100, 99, 98, 100)], initial_capital=1_000, costs=ZERO_COSTS)

    def test_timestamp_resolution_change_and_utc(self):
        first, unit1 = parse_binance_kline_row(make_kline_row(date(2018, 1, 1), unit=1_000))
        last, unit2 = parse_binance_kline_row(make_kline_row(date(2025, 1, 1), unit=1_000_000))
        self.assertEqual((first.session, unit1), ("2018-01-01", 1_000))
        self.assertEqual((last.session, unit2), ("2025-01-01", 1_000_000))

    def test_kline_row_rejects_wrong_close_time(self):
        row = make_kline_row(date(2025, 1, 1), unit=1_000_000)
        row[6] = str(int(row[6]) - 1)
        with self.assertRaisesRegex(ValueError, "close time"):
            parse_binance_kline_row(row)

    def test_monthly_loader_checks_hash_and_calendar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, [
                make_kline_row(date(2025, 1, 1), unit=1_000_000),
                make_kline_row(date(2025, 1, 2), unit=1_000_000),
            ])
            loaded = load_binance_vision_klines(
                root, start_session=date(2025, 1, 1), end_session=date(2025, 1, 2)
            )
            self.assertEqual([b.session for b in loaded.bars], ["2025-01-01", "2025-01-02"])
            self.assertEqual(loaded.archive_count, 1)
            self.assertEqual(loaded.microseconds_rows, 2)
            self.assertEqual(len(loaded.manifest_sha256), 64)

    def test_monthly_loader_rejects_bad_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, [make_kline_row(date(2025, 1, 1), unit=1_000_000)])
            (root / "BTCUSDT-1d-2025-01.zip.CHECKSUM").write_text(
                f"{'0' * 64}  BTCUSDT-1d-2025-01.zip\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                load_binance_vision_klines(root, start_session=date(2025, 1, 1), end_session=date(2025, 1, 1))

    def test_monthly_loader_rejects_missing_day(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, [
                make_kline_row(date(2025, 1, 1), unit=1_000_000),
                make_kline_row(date(2025, 1, 3), unit=1_000_000),
            ])
            with self.assertRaisesRegex(ValueError, "session grid"):
                load_binance_vision_klines(root, start_session=date(2025, 1, 1), end_session=date(2025, 1, 3))

    def test_constraints_derive_from_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "filters.json"
            snapshot.write_text(json.dumps({
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.00001000", "maxQty": "9000", "stepSize": "0.00001000"},
                    {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "125.26150288", "stepSize": "0"},
                    {"filterType": "NOTIONAL", "minNotional": "5", "applyMinToMarket": True,
                     "maxNotional": "9000000", "applyMaxToMarket": False},
                ],
            }), encoding="utf-8")
            rules = load_binance_quantity_constraints(snapshot)
            self.assertEqual(rules.min_quantity, 0.00001)
            self.assertEqual(rules.step_size, 0.00001)
            self.assertEqual(rules.max_quantity, 125.26150288)
            self.assertEqual(rules.min_notional, 5)


    def test_donchian_entry_and_exit_use_prior_completed_channel(self):
        policy = make_exp_strategy_policy("EXP-002", {"entry_lookback": 3, "exit_lookback": 2})
        breakout = make_bars([100, 100, 100, 102])
        self.assertEqual(policy(breakout, False, 0), SignalDecision("BUY", "exp002_channel_breakout"))
        current_bar_not_in_channel = make_bars([100, 110, 100, 105])
        self.assertIsNone(policy(current_bar_not_in_channel, False, 0))
        breakdown = make_bars([100, 100, 100, 90])
        self.assertEqual(policy(breakdown, True, 1), SignalDecision("SELL", "exp002_channel_exit"))

    def test_rsi_mean_reversion_exit_and_time_stop(self):
        policy = make_exp_strategy_policy("EXP-003", {
            "rsi_period": 2, "entry_threshold": 10, "exit_threshold": 50, "maximum_held_bars": 10,
        })
        oversold = make_bars([100, 99, 98])
        self.assertEqual(policy(oversold, False, 0), SignalDecision("BUY", "exp003_rsi_entry"))
        rebound = make_bars([100, 99, 98, 99, 100])
        self.assertEqual(policy(rebound, True, 1), SignalDecision("SELL", "exp003_rsi_exit"))
        self.assertEqual(policy(oversold, True, 10), SignalDecision("SELL", "exp003_time_stop"))

    def test_volatility_shock_uses_only_prior_true_ranges(self):
        policy = make_exp_strategy_policy("EXP-004", {"shock_multiple": 1.5, "maximum_held_bars": 2})
        bars = make_bars([100] * 15 + [103])
        last = bars[-1]
        bars[-1] = Bar(last.session, 100, 200, 99, 103)
        self.assertEqual(policy(bars, False, 0), SignalDecision("BUY", "exp004_volatility_shock"))

    def test_strategy_policy_executes_next_open_and_receives_only_causal_history(self):
        closes = [100, 110, 110, 90, 95]
        opens = closes.copy()
        opens[2], opens[4] = 150, 80
        bars = make_bars(closes, opens)
        observed_history_ends = []

        def policy(history, in_position, bars_held):
            observed_history_ends.append(history[-1].session)
            current = history[-1].close
            if not in_position and current > 105:
                return SignalDecision("BUY", "exp002_channel_breakout")
            if in_position and current < 95:
                return SignalDecision("SELL", "exp002_channel_exit")
            return None

        result = run_backtest(
            bars, initial_capital=10_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 1_000, 0), signal_policy=policy,
        )
        buy, sell = result.fills
        self.assertEqual((buy.signal_session, buy.fill_session, buy.reference_price),
                         (bars[1].session, bars[2].session, 150))
        self.assertEqual((sell.signal_session, sell.fill_session, sell.reference_price),
                         (bars[3].session, bars[4].session, 80))
        self.assertEqual(observed_history_ends, [bar.session for bar in bars[:-1]])

    def test_validation_policy_can_use_only_prior_warmup_without_carrying_position(self):
        all_bars = make_bars([100, 101, 102, 104, 105])
        history, validation = all_bars[:3], all_bars[3:]
        policy = make_exp_strategy_policy("EXP-002", {"entry_lookback": 3, "exit_lookback": 2})
        result = run_backtest(
            validation, initial_capital=10_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 1_000, 0), signal_policy=policy, signal_history=history,
        )
        buy = next(fill for fill in result.fills if fill.side == "BUY")
        self.assertEqual(buy.signal_session, validation[0].session)
        self.assertEqual(buy.fill_session, validation[1].session)
        self.assertEqual(result.equity_curve[0].quantity, 0)

    def test_volatility_policy_time_stop_uses_completed_holding_bars(self):
        closes = [100] * 15 + [103, 104, 105, 106]
        opens = closes.copy()
        opens[16], opens[18] = 110, 90
        bars = make_bars(closes, opens)
        policy = make_exp_strategy_policy("EXP-004", {"shock_multiple": 1.5, "maximum_held_bars": 2})
        result = run_backtest(
            bars, initial_capital=10_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 1_000, 0), signal_policy=policy,
        )
        buy, sell = result.fills
        self.assertEqual((buy.signal_session, buy.fill_session, buy.reference_price),
                         (bars[15].session, bars[16].session, 110))
        self.assertEqual((sell.signal_session, sell.fill_session, sell.reference_price, sell.reason),
                         (bars[17].session, bars[18].session, 90, "exp004_time_stop"))

    def test_monthly_loader_ignores_unrequested_archives_for_frozen_subperiods(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, [make_kline_row(date(2025, 1, 1), unit=1_000_000)])
            (root / "BTCUSDT-1d-2025-02.zip").write_bytes(b"not opened by the requested-period loader")
            loaded = load_binance_vision_klines(
                root, start_session=date(2025, 1, 1), end_session=date(2025, 1, 1)
            )
            self.assertEqual(len(loaded.bars), 1)
            self.assertEqual(loaded.bars[0].session, "2025-01-01")
            self.assertEqual(loaded.archive_count, 1)


    def test_eth_symbol_loader_and_quantity_constraints(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, [
                make_kline_row(date(2025, 1, 1), unit=1_000_000),
                make_kline_row(date(2025, 1, 2), unit=1_000_000),
            ], symbol="ETHUSDT")
            loaded = load_binance_vision_klines(
                root, start_session=date(2025, 1, 1), end_session=date(2025, 1, 2), symbol="ETHUSDT",
            )
            self.assertEqual(len(loaded.bars), 2)
            self.assertEqual(loaded.microseconds_rows, 2)
            self.assertEqual(loaded.bars[0].session, "2025-01-01")
            snapshot = root / "exchange_filters_snapshot.json"
            snapshot.write_text(json.dumps({
                "symbol": "ETHUSDT",
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.00010000", "maxQty": "9000", "stepSize": "0.00010000"},
                    {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "3296.98395916", "stepSize": "0"},
                    {"filterType": "NOTIONAL", "minNotional": "5", "applyMinToMarket": True,
                     "maxNotional": "9000000", "applyMaxToMarket": False},
                ],
            }), encoding="utf-8")
            rules = load_binance_quantity_constraints(snapshot, symbol="ETHUSDT")
            self.assertEqual(rules.min_quantity, 0.0001)
            self.assertEqual(rules.step_size, 0.0001)
            self.assertEqual(rules.max_quantity, 3296.98395916)
            self.assertEqual(rules.min_notional, 5)

    def test_trade_distribution_reports_quantiles_and_winner_concentration(self):
        closes = [100, 110, 100, 120, 130, 130, 100, 90, 80, 80]
        bars = make_bars(closes)

        def policy(history, in_position, bars_held):
            count = len(history)
            if not in_position and count in (2, 6):
                return SignalDecision("BUY", "exp002_channel_breakout")
            if in_position and count in (4, 8):
                return SignalDecision("SELL", "exp002_channel_exit")
            return None

        result = run_backtest(
            bars, initial_capital=1_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(1, 1, 100, 0), signal_policy=policy,
        )
        distribution = _trade_distribution(result)
        self.assertEqual(distribution["trade_count"], 2)
        self.assertEqual(distribution["winner_count"], 1)
        self.assertEqual(distribution["loser_count"], 1)
        self.assertEqual(distribution["top_1_winner_share_pct"], 100)
        self.assertEqual(distribution["top_3_winner_share_pct"], 100)
        self.assertGreater(distribution["p95_net_pnl_usdt"], distribution["p05_net_pnl_usdt"])


    def test_h4_parser_keeps_utc_open_close_and_quote_volume(self):
        row = make_kline_row(
            date(2023, 12, 31), unit=1_000, interval="4h", hour=20,
            open_price="100", high="105", low="99", close="104", quote_volume="2500",
        )
        bar, unit = parse_binance_kline_row(row, interval="4h")
        self.assertEqual(unit, 1_000)
        self.assertEqual(bar.session, "2023-12-31T20:00:00Z")
        self.assertEqual(bar.close_time, "2023-12-31T23:59:59.999Z")
        self.assertEqual(bar.quote_volume, 2500)
        bad_grid = make_kline_row(date(2023, 12, 31), unit=1_000, interval="4h", hour=2)
        with self.assertRaisesRegex(ValueError, "four-hour grid"):
            parse_binance_kline_row(bad_grid, interval="4h")
        bad_close = row.copy()
        bad_close[6] = str(int(bad_close[6]) - 1)
        with self.assertRaisesRegex(ValueError, "close time"):
            parse_binance_kline_row(bad_close, interval="4h")

    def test_h4_loader_requires_six_bars_per_utc_day_across_midnight(self):
        rows = [
            make_kline_row(day, unit=1_000, interval="4h", hour=hour)
            for day in (date(2023, 12, 30), date(2023, 12, 31))
            for hour in (0, 4, 8, 12, 16, 20)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, rows, interval="4h", archive_month="2023-12")
            loaded = load_binance_vision_klines(
                root, start_session=date(2023, 12, 30), end_session=date(2023, 12, 31),
                symbol="BTCUSDT", interval="4h",
            )
            self.assertEqual(len(loaded.bars), 12)
            self.assertEqual(loaded.archive_count, 1)
            self.assertEqual(loaded.bars[5].session, "2023-12-30T20:00:00Z")
            self.assertEqual(loaded.bars[6].session, "2023-12-31T00:00:00Z")
            self.assertEqual(loaded.bars[-1].session, "2023-12-31T20:00:00Z")
        missing = rows[:8] + rows[9:]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture_dataset(root, missing, interval="4h", archive_month="2023-12")
            with self.assertRaisesRegex(ValueError, "4h UTC session grid"):
                load_binance_vision_klines(
                    root, start_session=date(2023, 12, 30), end_session=date(2023, 12, 31),
                    symbol="BTCUSDT", interval="4h",
                )

    def test_h4_compression_breakout_uses_prior_ranges_volume_and_channel(self):
        closes = [100.0] * 31
        highs = [100.5] + [102.0] * 24 + [100.5] * 6
        lows = [99.5] + [98.0] * 24 + [99.5] * 6
        history = make_h4_bars(closes, highs=highs, lows=lows)
        trigger = make_h4_bars(
            [104.0], opens=[100.0], highs=[105.0], lows=[99.5], quote_volumes=[150.0],
            first=datetime(2020, 1, 6, 4, tzinfo=timezone.utc),
        )[0]
        policy = make_exp_strategy_policy("EXP-005", {"breakout_lookback": 12})
        self.assertEqual(policy(history + [trigger], False, 0), SignalDecision("BUY", "exp005_compression_breakout"))
        policy_24 = make_exp_strategy_policy("EXP-005", {"breakout_lookback": 24})
        self.assertEqual(policy_24(history + [trigger], False, 0), SignalDecision("BUY", "exp005_compression_breakout"))
        no_breakout = Bar(trigger.session, 100.0, 105.0, 99.5, 101.0, 150.0, trigger.close_time)
        self.assertIsNone(policy(history + [no_breakout], False, 0))
        low_volume = Bar(trigger.session, 100.0, 105.0, 99.5, 104.0, 124.0, trigger.close_time)
        self.assertIsNone(policy(history + [low_volume], False, 0))
        breakdown = Bar(trigger.session, 100.0, 100.0, 89.0, 90.0, 100.0, trigger.close_time)
        self.assertEqual(policy(history + [breakdown], True, 1), SignalDecision("SELL", "exp005_trailing_exit"))
        self.assertEqual(policy(history + [trigger], True, 18), SignalDecision("SELL", "exp005_time_stop"))

    def test_h4_high_volume_shock_and_next_open_execution(self):
        stable_closes = [100.0] * 25
        stable_highs = [101.0] * 25
        stable_lows = [99.0] * 25
        shock = make_h4_bars(
            [95.0], opens=[100.0], highs=[100.0], lows=[94.0], quote_volumes=[300.0],
            first=datetime(2020, 1, 5, 4, tzinfo=timezone.utc),
        )[0]
        policy = make_exp_strategy_policy("EXP-006", {"shock_multiple": 2.5})
        history = make_h4_bars(stable_closes, highs=stable_highs, lows=stable_lows)
        self.assertEqual(policy(history + [shock], False, 0), SignalDecision("BUY", "exp006_capitulation_entry"))
        policy_20 = make_exp_strategy_policy("EXP-006", {"shock_multiple": 2.0})
        self.assertEqual(policy_20(history + [shock], False, 0), SignalDecision("BUY", "exp006_capitulation_entry"))
        quiet_shock = Bar(shock.session, shock.open, shock.high, shock.low, shock.close, 199.0, shock.close_time)
        self.assertIsNone(policy(history + [quiet_shock], False, 0))
        recovery = make_h4_bars([100.0] * 6 + [101.0])
        self.assertEqual(policy(recovery, True, 1), SignalDecision("SELL", "exp006_reversion_exit"))
        self.assertEqual(policy(recovery, True, 12), SignalDecision("SELL", "exp006_time_stop"))

        post_shock = make_h4_bars(
            [95.0, 95.0], opens=[110.0, 95.0], highs=[111.0, 96.0], lows=[94.0, 94.0],
            quote_volumes=[100.0, 100.0], first=datetime(2020, 1, 5, 8, tzinfo=timezone.utc),
        )
        bars = history + [shock] + post_shock
        result = run_backtest(
            bars, initial_capital=10_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(0.0001, 0.0001, 1_000, 0), signal_policy=policy,
        )
        buy = next(fill for fill in result.fills if fill.side == "BUY")
        sell = next(fill for fill in result.fills if fill.side == "SELL")
        self.assertEqual(buy.signal_session, shock.session)
        self.assertEqual(buy.fill_session, post_shock[0].session)
        self.assertEqual(buy.reference_price, post_shock[0].open)
        self.assertEqual(sell.fill_session, bars[-1].close_time)
        self.assertEqual(_trade_duration_summary(result)["trade_count"], 1)
        self.assertEqual(_trade_duration_summary(result)["max_bars"], 2)

    def test_h4_metrics_include_the_full_utc_end_day(self):
        bars = make_h4_bars([100.0 + i for i in range(12)])
        result = run_buy_and_hold(
            bars, initial_capital=1_000, costs=ZERO_COSTS,
            constraints=QuantityConstraints(0.0001, 0.0001, 100, 0),
        )
        metrics = compute_window_metrics(
            result, start_session=date(2020, 1, 2), end_session=date(2020, 1, 2)
        )
        self.assertEqual(metrics.starting_equity, result.equity_curve[5].equity)
        self.assertEqual(metrics.final_equity, result.equity_curve[11].equity)
        self.assertEqual(metrics.exposure_pct, 100 * 5 / 6)


if __name__ == "__main__":
    unittest.main()
