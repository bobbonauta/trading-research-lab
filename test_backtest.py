"""Synthetic checks for EXP-001 ingestion, accounting, and window metrics."""
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
    compute_window_metrics,
    load_binance_quantity_constraints,
    load_binance_vision_klines,
    parse_binance_kline_row,
    run_backtest,
    run_buy_and_hold,
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


def make_kline_row(session, *, unit, open_price="100", high="102", low="99", close="101"):
    opened = datetime.combine(session, datetime.min.time(), tzinfo=timezone.utc)
    open_ts = int(opened.timestamp()) * unit
    close_ts = open_ts + 86_400 * unit - 1
    return [
        str(open_ts), open_price, high, low, close, "12.5", str(close_ts),
        "1250.0", "42", "6.0", "600.0", "0",
    ]


def write_fixture_dataset(root: Path, rows):
    root.mkdir(parents=True, exist_ok=True)
    name = "BTCUSDT-1d-2025-01.zip"
    csv_name = "BTCUSDT-1d-2025-01.csv"
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


if __name__ == "__main__":
    unittest.main()
