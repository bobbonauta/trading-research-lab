"""Minimal deterministic daily-bar engine for the EXP-001 SMA crossover.

Signals are evaluated at each completed close and filled no earlier than the
next bar open. This prototype assumes whole units, cash-only long exposure, and
full fills. It is not a broker simulator and makes no market-data claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import floor, fsum, isfinite
from statistics import fmean
from typing import Literal, Sequence

FAST_PERIOD = 20
SLOW_PERIOD = 100
Side = Literal["BUY", "SELL"]
Reason = Literal["sma_cross", "end_of_test"]


@dataclass(frozen=True)
class Bar:
    session: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class CostModel:
    commission_bps: float
    spread_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        values = (self.commission_bps, self.spread_bps, self.slippage_bps)
        if any(not isinstance(value, (int, float)) or not isfinite(value) or value < 0 for value in values):
            raise ValueError("costs must be finite, non-negative basis-point values")
        if self.spread_bps / 2 + self.slippage_bps >= 10_000:
            raise ValueError("spread and slippage must leave a positive sell price")


@dataclass(frozen=True)
class Fill:
    side: Side
    reason: Reason
    signal_session: str | None
    fill_session: str
    reference_price: float
    fill_price: float
    quantity: int
    commission: float


@dataclass(frozen=True)
class RejectedOrder:
    side: Side
    reason: Reason
    signal_session: str
    attempted_session: str
    detail: str


@dataclass(frozen=True)
class Trade:
    entry: Fill
    exit: Fill
    gross_pnl: float
    total_costs: float
    net_pnl: float
    return_on_entry_cost: float


@dataclass(frozen=True)
class EquityPoint:
    session: str
    cash: float
    quantity: int
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    initial_capital: float
    final_capital: float
    fills: tuple[Fill, ...]
    rejected_orders: tuple[RejectedOrder, ...]
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    total_costs: float
    return_fraction: float


def _validate_bars(bars: Sequence[Bar]) -> tuple[Bar, ...]:
    data = tuple(bars)
    if not data:
        raise ValueError("at least one bar is required")

    previous_session: date | None = None
    for index, bar in enumerate(data):
        if not isinstance(bar, Bar):
            raise ValueError(f"bar {index} is not a Bar")
        try:
            parsed_session = date.fromisoformat(bar.session)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"bar {index} has an invalid ISO session date") from exc
        if parsed_session.isoformat() != bar.session:
            raise ValueError(f"bar {index} session must use YYYY-MM-DD")
        if previous_session is not None and parsed_session <= previous_session:
            raise ValueError("bar sessions must be strictly increasing")
        previous_session = parsed_session

        prices = (bar.open, bar.high, bar.low, bar.close)
        if any(not isinstance(price, (int, float)) or not isfinite(price) or price <= 0 for price in prices):
            raise ValueError(f"bar {index} has a missing, non-finite, or non-positive OHLC value")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
            raise ValueError(f"bar {index} has inconsistent OHLC values")
    return data


def _execution_price(reference_price: float, side: Side, costs: CostModel) -> float:
    impact = (costs.spread_bps / 2 + costs.slippage_bps) / 10_000
    return reference_price * (1 + impact if side == "BUY" else 1 - impact)


def _commission(price: float, quantity: int, costs: CostModel) -> float:
    return price * quantity * costs.commission_bps / 10_000


def run_backtest(
    bars: Sequence[Bar],
    *,
    initial_capital: float,
    costs: CostModel,
) -> BacktestResult:
    """Run the frozen SMA(20)/SMA(100), long-only rule on validated daily bars.

    Orders signalled at a close are attempted at the following bar's open. The
    engine uses whole units, never borrows, and assumes full fills. A pending
    signal without an available next bar is ignored. Any open position is
    liquidated at the final bar close with the same cost model.
    """
    data = _validate_bars(bars)
    if not isinstance(initial_capital, (int, float)) or not isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be a finite positive number")
    if not isinstance(costs, CostModel):
        raise ValueError("costs must be a CostModel")

    capital = float(initial_capital)
    cash = capital
    quantity = 0
    entry_fill: Fill | None = None
    pending: tuple[Side, str] | None = None
    fills: list[Fill] = []
    rejected: list[RejectedOrder] = []
    trades: list[Trade] = []
    equity_curve: list[EquityPoint] = []
    closes = [float(bar.close) for bar in data]

    for index, bar in enumerate(data):
        if pending is not None:
            side, signal_session = pending
            if side == "BUY":
                if quantity != 0:
                    rejected.append(RejectedOrder(side, "sma_cross", signal_session, bar.session, "already_in_position"))
                else:
                    fill_price = _execution_price(float(bar.open), side, costs)
                    unit_cash = fill_price * (1 + costs.commission_bps / 10_000)
                    buy_quantity = floor((cash + 1e-10) / unit_cash)
                    if buy_quantity < 1:
                        rejected.append(RejectedOrder(side, "sma_cross", signal_session, bar.session, "insufficient_cash_for_one_unit"))
                    else:
                        fee = _commission(fill_price, buy_quantity, costs)
                        fill = Fill(side, "sma_cross", signal_session, bar.session, float(bar.open), fill_price, buy_quantity, fee)
                        cash -= buy_quantity * fill_price + fee
                        if cash < 0 and cash > -1e-8:
                            cash = 0.0
                        if cash < 0:
                            raise ArithmeticError("cash balance became negative")
                        quantity = buy_quantity
                        entry_fill = fill
                        fills.append(fill)
            else:
                if quantity < 1 or entry_fill is None:
                    rejected.append(RejectedOrder(side, "sma_cross", signal_session, bar.session, "no_open_position"))
                else:
                    fill_price = _execution_price(float(bar.open), side, costs)
                    fee = _commission(fill_price, quantity, costs)
                    fill = Fill(side, "sma_cross", signal_session, bar.session, float(bar.open), fill_price, quantity, fee)
                    cash += quantity * fill_price - fee
                    gross_pnl = quantity * (fill.reference_price - entry_fill.reference_price)
                    entry_costs = quantity * (entry_fill.fill_price - entry_fill.reference_price) + entry_fill.commission
                    exit_costs = quantity * (fill.reference_price - fill.fill_price) + fill.commission
                    total_trade_costs = fsum((entry_costs, exit_costs))
                    net_pnl = gross_pnl - total_trade_costs
                    entry_cost = quantity * entry_fill.fill_price + entry_fill.commission
                    trades.append(Trade(entry_fill, fill, gross_pnl, total_trade_costs, net_pnl, net_pnl / entry_cost))
                    fills.append(fill)
                    quantity = 0
                    entry_fill = None
            pending = None

        is_final_bar = index == len(data) - 1
        if is_final_bar and quantity > 0 and entry_fill is not None:
            reference_price = float(bar.close)
            fill_price = _execution_price(reference_price, "SELL", costs)
            fee = _commission(fill_price, quantity, costs)
            fill = Fill("SELL", "end_of_test", None, bar.session, reference_price, fill_price, quantity, fee)
            cash += quantity * fill_price - fee
            gross_pnl = quantity * (fill.reference_price - entry_fill.reference_price)
            entry_costs = quantity * (entry_fill.fill_price - entry_fill.reference_price) + entry_fill.commission
            exit_costs = quantity * (fill.reference_price - fill.fill_price) + fill.commission
            total_trade_costs = fsum((entry_costs, exit_costs))
            net_pnl = gross_pnl - total_trade_costs
            entry_cost = quantity * entry_fill.fill_price + entry_fill.commission
            trades.append(Trade(entry_fill, fill, gross_pnl, total_trade_costs, net_pnl, net_pnl / entry_cost))
            fills.append(fill)
            quantity = 0
            entry_fill = None

        equity = cash + quantity * float(bar.close)
        equity_curve.append(EquityPoint(bar.session, cash, quantity, equity))

        if is_final_bar or index < SLOW_PERIOD:
            continue

        previous_fast = fmean(closes[index - FAST_PERIOD:index])
        current_fast = fmean(closes[index - FAST_PERIOD + 1:index + 1])
        previous_slow = fmean(closes[index - SLOW_PERIOD:index])
        current_slow = fmean(closes[index - SLOW_PERIOD + 1:index + 1])

        crossed_up = previous_fast <= previous_slow and current_fast > current_slow
        crossed_down = previous_fast >= previous_slow and current_fast < current_slow
        if quantity == 0 and crossed_up:
            pending = ("BUY", bar.session)
        elif quantity > 0 and crossed_down:
            pending = ("SELL", bar.session)

    final_capital = cash
    return BacktestResult(
        initial_capital=capital,
        final_capital=final_capital,
        fills=tuple(fills),
        rejected_orders=tuple(rejected),
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
        total_costs=fsum(trade.total_costs for trade in trades),
        return_fraction=(final_capital - capital) / capital,
    )