"""Synthetic technical checks for the minimal EXP-001 engine."""
from datetime import date, timedelta
import math
import unittest

from backtest import Bar, CostModel, run_backtest


ZERO_COSTS = CostModel(commission_bps=0, spread_bps=0, slippage_bps=0)


def make_bars(closes, opens=None):
    opens = list(closes if opens is None else opens)
    result = []
    first = date(2020, 1, 1)
    for index, (open_price, close_price) in enumerate(zip(opens, closes)):
        high = max(open_price, close_price) + 1
        low = min(open_price, close_price) - 1
        result.append(Bar((first + timedelta(days=index)).isoformat(), open_price, high, low, close_price))
    return result


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

    def test_exit_cross_uses_next_open_and_gap_price(self):
        closes = [100.0] * 100 + list(map(float, range(101, 131))) + list(map(float, range(130, 79, -1)))
        opens = [close + 0.5 for close in closes]
        bars = make_bars(closes, opens)

        result = run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS)

        sell = next(fill for fill in result.fills if fill.side == "SELL" and fill.reason == "sma_cross")
        signal_index = next(i for i, bar in enumerate(bars) if bar.session == sell.signal_session)
        self.assertEqual(sell.fill_session, bars[signal_index + 1].session)
        self.assertEqual(sell.reference_price, bars[signal_index + 1].open)

    def test_costs_and_pnl_reconcile_with_final_capital(self):
        closes = [100.0] * 100 + [101.0, 102.0, 103.0, 104.0]
        opens = closes.copy()
        opens[101] = 200.0
        bars = make_bars(closes, opens)
        costs = CostModel(commission_bps=10, spread_bps=2, slippage_bps=1)

        result = run_backtest(bars, initial_capital=100_000, costs=costs)

        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.exit.reason, "end_of_test")
        self.assertGreater(result.total_costs, 0)
        self.assertAlmostEqual(trade.net_pnl, trade.gross_pnl - trade.total_costs, places=7)
        self.assertAlmostEqual(result.final_capital, result.initial_capital + trade.net_pnl, places=7)
        self.assertAlmostEqual(result.equity_curve[-1].equity, result.final_capital, places=7)
        self.assertLess(trade.net_pnl, 0)  # A losing synthetic trade is handled and reconciled.
        self.assertTrue(all(point.cash >= 0 and point.quantity >= 0 for point in result.equity_curve))

    def test_flat_series_has_no_trades_and_preserves_capital(self):
        bars = make_bars([100.0] * 120)
        result = run_backtest(bars, initial_capital=10_000, costs=ZERO_COSTS)

        self.assertEqual(result.trades, ())
        self.assertEqual(result.fills, ())
        self.assertEqual(result.final_capital, 10_000)
        self.assertEqual(result.total_costs, 0)

    def test_insufficient_cash_is_recorded_as_rejected_order(self):
        closes = [100.0] * 100 + [101.0, 102.0]
        bars = make_bars(closes)
        result = run_backtest(bars, initial_capital=50, costs=ZERO_COSTS)

        self.assertEqual(result.fills, ())
        self.assertEqual(len(result.rejected_orders), 1)
        self.assertEqual(result.rejected_orders[0].detail, "insufficient_cash_for_one_unit")

    def test_runs_are_reproducible(self):
        bars = make_bars([100.0] * 100 + [101.0, 102.0, 103.0, 104.0])
        first = run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS)
        second = run_backtest(bars, initial_capital=100_000, costs=ZERO_COSTS)
        self.assertEqual(first, second)

    def test_invalid_and_missing_ohlc_are_rejected(self):
        valid = make_bars([100.0, 101.0])
        missing = [valid[0], Bar(valid[1].session, float("nan"), 102.0, 100.0, 101.0)]
        duplicate_date = [valid[0], Bar(valid[0].session, 101.0, 102.0, 100.0, 101.0)]

        with self.assertRaisesRegex(ValueError, "OHLC"):
            run_backtest(missing, initial_capital=1_000, costs=ZERO_COSTS)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            run_backtest(duplicate_date, initial_capital=1_000, costs=ZERO_COSTS)

    def test_ohlc_inconsistency_is_rejected(self):
        bad = [Bar("2020-01-01", 100.0, 99.0, 98.0, 100.0)]
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            run_backtest(bad, initial_capital=1_000, costs=ZERO_COSTS)


if __name__ == "__main__":
    unittest.main()