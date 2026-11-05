"""Deterministic BTCUSDT daily-bar engine and Binance Vision loader."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from math import fsum, isfinite
from statistics import fmean
from pathlib import Path
from typing import Callable, Literal, Sequence

FAST_PERIOD = 20
SLOW_PERIOD = 100
Side = Literal["BUY", "SELL"]
Reason = Literal["sma_cross", "end_of_test", "benchmark", "exp002_channel_breakout", "exp002_channel_exit", "exp003_rsi_entry", "exp003_rsi_exit", "exp003_time_stop", "exp004_volatility_shock", "exp004_time_stop", "exp005_compression_breakout", "exp005_trailing_exit", "exp005_time_stop", "exp006_capitulation_entry", "exp006_reversion_exit", "exp006_time_stop"]
TIMESTAMP_SWITCH_DATE = date(2025, 1, 1)
DEFAULT_START = date(2018, 1, 1)
DEFAULT_END = date(2025, 12, 31)


@dataclass(frozen=True)
class Bar:
    session: str
    open: float
    high: float
    low: float
    close: float
    quote_volume: float | None = None
    close_time: str | None = None


@dataclass(frozen=True)
class CostModel:
    commission_bps: float
    spread_bps: float
    slippage_bps: float

    def __post_init__(self):
        values = (self.commission_bps, self.spread_bps, self.slippage_bps)
        if any(not isinstance(v, (int, float)) or not isfinite(v) or v < 0 for v in values):
            raise ValueError("costs must be finite non-negative basis-point values")
        if self.commission_bps >= 10_000 or self.spread_bps / 2 + self.slippage_bps >= 10_000:
            raise ValueError("costs must leave a positive execution price")


@dataclass(frozen=True)
class QuantityConstraints:
    min_quantity: float = 1.0
    step_size: float = 1.0
    max_quantity: float | None = None
    min_notional: float = 0.0

    def __post_init__(self):
        if not isfinite(self.min_quantity) or self.min_quantity <= 0:
            raise ValueError("min_quantity must be finite and positive")
        if not isfinite(self.step_size) or self.step_size <= 0:
            raise ValueError("step_size must be finite and positive")
        if self.max_quantity is not None and (
            not isfinite(self.max_quantity) or self.max_quantity < self.min_quantity
        ):
            raise ValueError("max_quantity must be finite and >= min_quantity")
        if not isfinite(self.min_notional) or self.min_notional < 0:
            raise ValueError("min_notional must be finite and non-negative")


WHOLE_UNIT_CONSTRAINTS = QuantityConstraints()


@dataclass(frozen=True)
class SignalDecision:
    action: Side
    reason: Reason


SignalPolicy = Callable[[Sequence[Bar], bool, int], SignalDecision | None]


@dataclass(frozen=True)
class Fill:
    side: Side
    reason: Reason
    signal_session: str | None
    fill_session: str
    reference_price: float
    fill_price: float
    quantity: float
    commission: float


@dataclass(frozen=True)
class RejectedOrder:
    side: Side
    reason: Reason
    signal_session: str | None
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
    quantity: float
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


@dataclass(frozen=True)
class LoadedDataset:
    bars: tuple[Bar, ...]
    archive_count: int
    milliseconds_rows: int
    microseconds_rows: int
    manifest_sha256: str


@dataclass(frozen=True)
class WindowMetrics:
    start_session: str
    end_session: str
    starting_equity: float
    final_equity: float
    net_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    profit_factor: float | None
    expectancy_usdt: float | None
    win_rate_pct: float | None
    exposure_pct: float
    total_costs_usdt: float


def _format_utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    value = value.astimezone(timezone.utc)
    if value.microsecond == 0:
        precision = "seconds"
    elif value.microsecond % 1000 == 0:
        precision = "milliseconds"
    else:
        precision = "microseconds"
    return value.isoformat(timespec=precision).replace("+00:00", "Z")


def _bar_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("bar timestamp must be a string")
    if len(value) == 10:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("bar has invalid ISO session date") from exc
        if parsed_date.isoformat() != value:
            raise ValueError("daily bar session must use YYYY-MM-DD")
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    if not value.endswith("Z"):
        raise ValueError("intraday bar timestamp must be explicit UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("bar has invalid ISO UTC timestamp") from exc
    if _format_utc_timestamp(parsed) != value:
        raise ValueError("intraday bar timestamp is not canonical UTC")
    return parsed


def _validate_bars(bars: Sequence[Bar]) -> tuple[Bar, ...]:
    data = tuple(bars)
    if not data:
        raise ValueError("at least one bar is required")
    previous = None
    for index, bar in enumerate(data):
        if not isinstance(bar, Bar):
            raise ValueError(f"bar {index} is not a Bar")
        try:
            parsed = _bar_datetime(bar.session)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"bar {index} has invalid ISO UTC timestamp") from exc
        if previous is not None and parsed <= previous:
            raise ValueError("bar sessions must be strictly increasing")
        previous = parsed
        prices = (bar.open, bar.high, bar.low, bar.close)
        if any(not isinstance(v, (int, float)) or not isfinite(v) or v <= 0 for v in prices):
            raise ValueError(f"bar {index} has missing, non-finite, or non-positive OHLC")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
            raise ValueError(f"bar {index} has inconsistent OHLC values")
        if bar.quote_volume is not None and (
            not isinstance(bar.quote_volume, (int, float)) or not isfinite(bar.quote_volume) or bar.quote_volume < 0
        ):
            raise ValueError(f"bar {index} has invalid quote volume")
        if bar.close_time is not None:
            try:
                closed = _bar_datetime(bar.close_time)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"bar {index} has invalid close timestamp") from exc
            if closed <= parsed:
                raise ValueError(f"bar {index} close timestamp must follow its open timestamp")
    return data


def _timestamp(value: str, label: str) -> tuple[datetime, int, int]:
    try:
        ts = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer timestamp") from exc
    if ts < 0:
        raise ValueError(f"{label} cannot be negative")
    unit = 1_000_000 if ts >= 10**14 else 1_000
    seconds, remainder = divmod(ts, unit)
    micros = remainder if unit == 1_000_000 else remainder * 1_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=micros), unit, ts


INTERVAL_SECONDS = {"1d": 86_400, "4h": 14_400}


def parse_binance_kline_row(
    row: Sequence[str], *, source: str = "kline", interval: str = "1d"
) -> tuple[Bar, int]:
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"{source}: unsupported kline interval {interval}")
    if len(row) != 12:
        raise ValueError(f"{source}: expected 12 CSV columns, found {len(row)}")
    opened, unit, open_ts = _timestamp(row[0], f"{source} open time")
    closed, close_unit, close_ts = _timestamp(row[6], f"{source} close time")
    if close_unit != unit or close_ts != open_ts + INTERVAL_SECONDS[interval] * unit - 1:
        raise ValueError(f"{source}: close time does not match a {interval} UTC candle")
    if (unit == 1_000_000) != (opened.date() >= TIMESTAMP_SWITCH_DATE):
        raise ValueError(f"{source}: timestamp unit disagrees with Binance's 2025 change")
    if interval == "1d":
        if opened.hour or opened.minute or opened.second or opened.microsecond:
            raise ValueError(f"{source}: daily open is not midnight UTC")
        session = opened.date().isoformat()
        close_time = None
    else:
        if opened.hour % 4 or opened.minute or opened.second or opened.microsecond:
            raise ValueError(f"{source}: 4h open is not aligned to the UTC four-hour grid")
        session = _format_utc_timestamp(opened)
        close_time = _format_utc_timestamp(closed)
    try:
        values = [Decimal(value) for value in row]
        o, h, low, c = values[1:5]
        base_volume, quote_volume = values[5], values[7]
        checked_volumes = (values[5], values[7], values[9], values[10])
        trade_count = int(row[8])
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{source}: malformed numeric field") from exc
    if any(not v.is_finite() or v <= 0 for v in (o, h, low, c)):
        raise ValueError(f"{source}: OHLC must be finite and positive")
    if h < max(o, c) or low > min(o, c) or h < low:
        raise ValueError(f"{source}: inconsistent OHLC")
    if any(not v.is_finite() or v < 0 for v in checked_volumes) or trade_count < 0:
        raise ValueError(f"{source}: invalid volume or trade count")
    return Bar(session, float(o), float(h), float(low), float(c), float(quote_volume), close_time), unit


def _month_names(
    start: date, end: date, *, symbol: str = "BTCUSDT", interval: str = "1d"
) -> tuple[str, ...]:
    if start > end:
        raise ValueError("start date must not follow end date")
    if not symbol or not symbol.isalnum():
        raise ValueError("symbol must contain only letters and digits")
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"unsupported kline interval {interval}")
    names = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        names.append(f"{symbol}-{interval}-{year:04d}-{month:02d}.zip")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(names)


def _expected_bar_opens(start: date, end: date, interval: str) -> tuple[str, ...]:
    if start > end:
        raise ValueError("start date must not follow end date")
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"unsupported kline interval {interval}")
    step = timedelta(seconds=INTERVAL_SECONDS[interval])
    current = datetime.combine(start, time.min, tzinfo=timezone.utc)
    final_open = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc) - step
    result = []
    while current <= final_open:
        result.append(current.date().isoformat() if interval == "1d" else _format_utc_timestamp(current))
        current += step
    return tuple(result)


def _expected_sessions(start: date, end: date) -> tuple[str, ...]:
    return _expected_bar_opens(start, end, "1d")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_binance_vision_klines(
    dataset_dir: str | Path, *, start_session: date = DEFAULT_START, end_session: date = DEFAULT_END,
    symbol: str = "BTCUSDT", interval: str = "1d",
) -> LoadedDataset:
    root = Path(dataset_dir)
    manifest_path = root / "download_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing dataset manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("dataset manifest is unreadable") from exc
    expected_files = _month_names(start_session, end_session, symbol=symbol, interval=interval)
    actual_files = {p.name for p in root.glob(f"{symbol}-{interval}-????-??.zip")}
    if not set(expected_files).issubset(actual_files):
        raise ValueError("monthly archive set is missing files for requested period")
    records = manifest.get("archives")
    if not isinstance(records, list):
        raise ValueError("dataset manifest has no archive records")
    record_map = {r.get("file"): r for r in records if isinstance(r, dict)}
    if len(record_map) != len(records) or not set(expected_files).issubset(record_map):
        raise ValueError("manifest archive list is missing or duplicated")

    bars, units = [], []
    for name in expected_files:
        archive_path = root / name
        checksum_path = root / f"{name}.CHECKSUM"
        if not checksum_path.is_file():
            raise ValueError(f"missing official checksum: {checksum_path.name}")
        tokens = checksum_path.read_text(encoding="utf-8-sig").strip().split()
        if not tokens or len(tokens[0].lstrip("*")) != 64:
            raise ValueError(f"malformed official checksum: {checksum_path.name}")
        actual_sha = _sha256_file(archive_path)
        if actual_sha != tokens[0].lstrip("*").lower() or actual_sha != str(record_map[name].get("sha256", "")).lower():
            raise ValueError(f"SHA-256 mismatch: {name}")
        try:
            with zipfile.ZipFile(archive_path) as archive:
                if archive.testzip() is not None:
                    raise ValueError(f"ZIP CRC check failed: {name}")
                csv_name = name[:-4] + ".csv"
                csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if csv_names != [csv_name]:
                    raise ValueError(f"unexpected CSV contents in {name}")
                with archive.open(csv_name, "r") as binary:
                    reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
                    for row_no, row in enumerate(reader, 1):
                        bar, unit = parse_binance_kline_row(row, source=f"{name}:{row_no}", interval=interval)
                        if start_session.isoformat() <= bar.session[:10] <= end_session.isoformat():
                            bars.append(bar)
                            units.append(unit)
        except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
            raise ValueError(f"cannot read archive {name}") from exc

    data = _validate_bars(bars)
    if tuple(b.session for b in data) != _expected_bar_opens(start_session, end_session, interval):
        label = "daily" if interval == "1d" else interval
        raise ValueError(f"{label} UTC session grid has duplicates or missing bars")
    return LoadedDataset(
        data, len(expected_files), units.count(1_000), units.count(1_000_000), _sha256_file(manifest_path)
    )


def load_binance_quantity_constraints(snapshot_path: str | Path, *, symbol: str = "BTCUSDT") -> QuantityConstraints:
    try:
        snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8-sig"))
        if snapshot.get("symbol") != symbol:
            raise ValueError(f"snapshot is not {symbol}")
        filters = {item["filterType"]: item for item in snapshot["filters"]}
        lot, market = filters["LOT_SIZE"], filters["MARKET_LOT_SIZE"]
        notional = filters.get("NOTIONAL")
        min_notional_filter = filters.get("MIN_NOTIONAL")
        min_qty = max(Decimal(lot["minQty"]), Decimal(market["minQty"]))
        market_step, lot_step = Decimal(market["stepSize"]), Decimal(lot["stepSize"])
        step = market_step if market_step > 0 else lot_step
        maxima = [Decimal(lot["maxQty"]), Decimal(market["maxQty"])]
        maxima = [value for value in maxima if value > 0]
        max_qty = min(maxima) if maxima else None
        if notional is not None:
            min_value = Decimal(notional["minNotional"]) if notional.get("applyMinToMarket", False) else Decimal(0)
        elif min_notional_filter is not None and min_notional_filter.get("applyToMarket", False):
            min_value = Decimal(min_notional_filter["minNotional"])
        else:
            min_value = Decimal(0)
        return QuantityConstraints(float(min_qty), float(step), float(max_qty) if max_qty else None, float(min_value))
    except (OSError, KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot derive {symbol} constraints from exchangeInfo snapshot") from exc


def _execution_price(reference: float, side: Side, costs: CostModel) -> float:
    impact = (costs.spread_bps / 2 + costs.slippage_bps) / 10_000
    return reference * (1 + impact if side == "BUY" else 1 - impact)


def _commission(price: float, quantity: float, costs: CostModel) -> float:
    return price * quantity * costs.commission_bps / 10_000


def _floor_to_step(quantity: float, step: float) -> float:
    steps = (Decimal(str(quantity)) / Decimal(str(step))).to_integral_value(rounding=ROUND_FLOOR)
    return float(steps * Decimal(str(step)))


def _reject_quantity(quantity: float, reference: float, rules: QuantityConstraints) -> str | None:
    tolerance = max(1e-12, rules.step_size * 1e-9)
    if quantity + tolerance < rules.min_quantity:
        return "below_minimum_quantity"
    if rules.max_quantity is not None and quantity > rules.max_quantity + tolerance:
        return "above_maximum_quantity"
    steps = Decimal(str(quantity)) / Decimal(str(rules.step_size))
    if steps != steps.to_integral_value():
        return "quantity_not_on_step"
    if quantity * reference + 1e-10 < rules.min_notional:
        return "below_minimum_notional"
    return None


def _fill_cost(fill: Fill) -> float:
    return abs(fill.fill_price - fill.reference_price) * fill.quantity + fill.commission


def _buy(cash: float, reference: float, session: str, signal: str | None, reason: Reason,
         costs: CostModel, rules: QuantityConstraints) -> tuple[Fill | None, str | None]:
    price = _execution_price(reference, "BUY", costs)
    unit_cash = price * (1 + costs.commission_bps / 10_000)
    desired = cash / unit_cash
    if rules.max_quantity is not None:
        desired = min(desired, rules.max_quantity)
    qty = _floor_to_step(desired, rules.step_size)
    if qty <= 0:
        return None, "insufficient_cash_for_minimum_quantity"
    rejection = _reject_quantity(qty, reference, rules)
    if rejection:
        return None, rejection
    fee = _commission(price, qty, costs)
    if price * qty + fee > cash + 1e-8:
        qty = _floor_to_step(cash / unit_cash, rules.step_size)
        rejection = _reject_quantity(qty, reference, rules)
        if rejection:
            return None, rejection
        fee = _commission(price, qty, costs)
    if price * qty + fee > cash + 1e-7:
        return None, "insufficient_cash"
    return Fill("BUY", reason, signal, session, reference, price, qty, fee), None


def _sell(quantity: float, entry: Fill, reference: float, session: str, signal: str | None,
          reason: Reason, costs: CostModel, rules: QuantityConstraints) -> tuple[Fill | None, str | None]:
    rejection = _reject_quantity(quantity, reference, rules)
    if rejection:
        return None, rejection
    price = _execution_price(reference, "SELL", costs)
    fee = _commission(price, quantity, costs)
    return Fill("SELL", reason, signal, session, reference, price, quantity, fee), None


def _trade(entry: Fill, exit_fill: Fill) -> Trade:
    gross = entry.quantity * (exit_fill.reference_price - entry.reference_price)
    costs = fsum((_fill_cost(entry), _fill_cost(exit_fill)))
    net = gross - costs
    entry_value = entry.quantity * entry.fill_price + entry.commission
    return Trade(entry, exit_fill, gross, costs, net, net / entry_value)


def _run_inputs(bars, initial_capital, costs, constraints):
    data = _validate_bars(bars)
    if not isinstance(initial_capital, (int, float)) or not isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be finite and positive")
    if not isinstance(costs, CostModel) or not isinstance(constraints, QuantityConstraints):
        raise ValueError("invalid cost model or quantity constraints")
    return data


def _result(initial, cash, quantity, fills, rejected, trades, curve):
    final = curve[-1].equity
    return BacktestResult(initial, final, tuple(fills), tuple(rejected), tuple(trades), tuple(curve),
                          fsum(_fill_cost(fill) for fill in fills), (final - initial) / initial)


def run_backtest(
    bars: Sequence[Bar], *, initial_capital: float, costs: CostModel,
    constraints: QuantityConstraints = WHOLE_UNIT_CONSTRAINTS,
    signal_policy: SignalPolicy | None = None,
    signal_history: Sequence[Bar] = (),
) -> BacktestResult:
    data = _run_inputs(bars, initial_capital, costs, constraints)
    prefix = tuple(signal_history)
    if prefix:
        prefix = _validate_bars(prefix)
        if prefix[-1].session >= data[0].session:
            raise ValueError("signal history must end before the simulated bars")
    if signal_policy is None and prefix:
        raise ValueError("signal_history requires a signal_policy")

    initial, cash, qty = float(initial_capital), float(initial_capital), 0.0
    entry = None
    entry_index = None
    pending: tuple[Side, str, Reason] | None = None
    fills, rejected, trades, curve = [], [], [], []
    closes = [float(bar.close) for bar in data]
    for i, bar in enumerate(data):
        if pending is not None:
            side, signal, reason = pending
            if side == "BUY" and qty == 0:
                fill, detail = _buy(cash, float(bar.open), bar.session, signal, reason, costs, constraints)
                if fill is None:
                    rejected.append(RejectedOrder(side, reason, signal, bar.session, detail or "rejected"))
                else:
                    cash -= fill.quantity * fill.fill_price + fill.commission
                    if cash < 0 and cash > -1e-7:
                        cash = 0.0
                    if cash < 0:
                        raise ArithmeticError("cash balance became negative")
                    qty, entry, entry_index = fill.quantity, fill, i
                    fills.append(fill)
            elif side == "SELL" and qty > 0 and entry is not None:
                fill, detail = _sell(qty, entry, float(bar.open), bar.session, signal, reason, costs, constraints)
                if fill is None:
                    rejected.append(RejectedOrder(side, reason, signal, bar.session, detail or "rejected"))
                else:
                    cash += qty * fill.fill_price - fill.commission
                    trades.append(_trade(entry, fill))
                    fills.append(fill)
                    qty, entry, entry_index = 0.0, None, None
            else:
                rejected.append(RejectedOrder(side, reason, signal, bar.session, "position_state_mismatch"))
            pending = None

        final_bar = i == len(data) - 1
        if final_bar and qty > 0 and entry is not None:
            fill, detail = _sell(qty, entry, float(bar.close), bar.close_time or bar.session, None, "end_of_test", costs, constraints)
            if fill is None:
                rejected.append(RejectedOrder("SELL", "end_of_test", None, bar.session, detail or "rejected"))
            else:
                cash += qty * fill.fill_price - fill.commission
                trades.append(_trade(entry, fill))
                fills.append(fill)
                qty, entry, entry_index = 0.0, None, None
        curve.append(EquityPoint(bar.session, cash, qty, cash + qty * float(bar.close)))
        if final_bar:
            continue

        if signal_policy is None:
            if i < SLOW_PERIOD:
                continue
            previous_fast = fmean(closes[i - FAST_PERIOD:i])
            current_fast = fmean(closes[i - FAST_PERIOD + 1:i + 1])
            previous_slow = fmean(closes[i - SLOW_PERIOD:i])
            current_slow = fmean(closes[i - SLOW_PERIOD + 1:i + 1])
            up = previous_fast <= previous_slow and current_fast > current_slow
            down = previous_fast >= previous_slow and current_fast < current_slow
            decision = SignalDecision("BUY", "sma_cross") if qty == 0 and up else (
                SignalDecision("SELL", "sma_cross") if qty > 0 and down else None
            )
        else:
            history = prefix + data[:i + 1]
            bars_held = i - entry_index + 1 if entry_index is not None else 0
            decision = signal_policy(history, qty > 0, bars_held)
            if decision is not None and not isinstance(decision, SignalDecision):
                raise ValueError("signal policy must return SignalDecision or None")

        if decision is not None:
            if qty == 0 and decision.action == "BUY":
                pending = (decision.action, bar.session, decision.reason)
            elif qty > 0 and decision.action == "SELL":
                pending = (decision.action, bar.session, decision.reason)
    return _result(initial, cash, qty, fills, rejected, trades, curve)


def _simple_rsi(history: Sequence[Bar], period: int) -> float | None:
    if period <= 0 or len(history) < period + 1:
        return None
    changes = [history[i].close - history[i - 1].close for i in range(len(history) - period, len(history))]
    gains = fmean(max(change, 0.0) for change in changes)
    losses = fmean(max(-change, 0.0) for change in changes)
    if gains == 0 and losses == 0:
        return 50.0
    if losses == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def _true_range_at(history: Sequence[Bar], index: int) -> float:
    if index <= 0 or index >= len(history):
        raise ValueError("true range requires a bar and its prior close")
    bar, previous = history[index], history[index - 1]
    return max(bar.high - bar.low, abs(bar.high - previous.close), abs(bar.low - previous.close))


def _mean_quote_volume(bars: Sequence[Bar]) -> float | None:
    if not bars or any(bar.quote_volume is None for bar in bars):
        return None
    return fmean(float(bar.quote_volume) for bar in bars)


def make_exp_strategy_policy(experiment_id: str, parameters: dict) -> SignalPolicy:
    if experiment_id == "EXP-002":
        entry_lookback = int(parameters["entry_lookback"])
        exit_lookback = int(parameters["exit_lookback"])

        def donchian(history: Sequence[Bar], in_position: bool, bars_held: int) -> SignalDecision | None:
            current = history[-1]
            if in_position:
                if len(history) >= exit_lookback + 1:
                    prior_lows = [bar.low for bar in history[-exit_lookback - 1:-1]]
                    if current.close < min(prior_lows):
                        return SignalDecision("SELL", "exp002_channel_exit")
            elif len(history) >= entry_lookback + 1:
                prior_highs = [bar.high for bar in history[-entry_lookback - 1:-1]]
                if current.close > max(prior_highs):
                    return SignalDecision("BUY", "exp002_channel_breakout")
            return None

        return donchian

    if experiment_id == "EXP-003":
        period = int(parameters["rsi_period"])
        entry_threshold = float(parameters["entry_threshold"])
        exit_threshold = float(parameters["exit_threshold"])
        maximum_held_bars = int(parameters["maximum_held_bars"])

        def mean_reversion(history: Sequence[Bar], in_position: bool, bars_held: int) -> SignalDecision | None:
            value = _simple_rsi(history, period)
            if value is None:
                return None
            if in_position:
                if bars_held >= maximum_held_bars:
                    return SignalDecision("SELL", "exp003_time_stop")
                if value >= exit_threshold:
                    return SignalDecision("SELL", "exp003_rsi_exit")
            elif value <= entry_threshold:
                return SignalDecision("BUY", "exp003_rsi_entry")
            return None

        return mean_reversion

    if experiment_id == "EXP-004":
        shock_multiple = float(parameters["shock_multiple"])
        maximum_held_bars = int(parameters["maximum_held_bars"])
        atr_period = 14

        def volatility_shock(history: Sequence[Bar], in_position: bool, bars_held: int) -> SignalDecision | None:
            if in_position:
                if bars_held >= maximum_held_bars:
                    return SignalDecision("SELL", "exp004_time_stop")
                return None
            prior = history[:-1]
            if len(prior) < atr_period + 1:
                return None
            prior_window = prior[-atr_period:]
            ranges = []
            start = len(prior) - atr_period
            for index, bar in enumerate(prior_window, start):
                previous_close = prior[index - 1].close
                ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
            normalized_atr = fmean(ranges) / prior[-1].close
            positive_return = history[-1].close / prior[-1].close - 1.0
            if positive_return >= shock_multiple * normalized_atr:
                return SignalDecision("BUY", "exp004_volatility_shock")
            return None

        return volatility_shock

    if experiment_id == "EXP-005":
        breakout_lookback = int(parameters["breakout_lookback"])
        if breakout_lookback not in (12, 24):
            raise ValueError("EXP-005 breakout_lookback must be 12 or 24")

        def compression_breakout(history: Sequence[Bar], in_position: bool, bars_held: int) -> SignalDecision | None:
            index = len(history) - 1
            current = history[-1]
            if in_position:
                if bars_held >= 18:
                    return SignalDecision("SELL", "exp005_time_stop")
                if index >= 6 and current.close < min(bar.low for bar in history[index - 6:index]):
                    return SignalDecision("SELL", "exp005_trailing_exit")
                return None
            if index < 31 or current.quote_volume is None:
                return None
            short_ranges = [_true_range_at(history, i) for i in range(index - 6, index)]
            reference_ranges = [_true_range_at(history, i) for i in range(index - 30, index - 6)]
            reference_mean = fmean(reference_ranges)
            if reference_mean <= 0:
                return None
            prior_volumes = _mean_quote_volume(history[index - 24:index])
            if prior_volumes is None or prior_volumes <= 0:
                return None
            prior_highs = [bar.high for bar in history[index - breakout_lookback:index]]
            if (
                fmean(short_ranges) <= 0.65 * reference_mean
                and current.close > max(prior_highs)
                and current.quote_volume >= 1.25 * prior_volumes
            ):
                return SignalDecision("BUY", "exp005_compression_breakout")
            return None

        return compression_breakout

    if experiment_id == "EXP-006":
        shock_multiple = float(parameters["shock_multiple"])
        if shock_multiple not in (2.0, 2.5):
            raise ValueError("EXP-006 shock_multiple must be 2.0 or 2.5")

        def high_volume_shock_reversal(history: Sequence[Bar], in_position: bool, bars_held: int) -> SignalDecision | None:
            index = len(history) - 1
            current = history[-1]
            if in_position:
                if bars_held >= 12:
                    return SignalDecision("SELL", "exp006_time_stop")
                if index >= 6 and current.close >= fmean(bar.close for bar in history[index - 6:index]):
                    return SignalDecision("SELL", "exp006_reversion_exit")
                return None
            if index < 25 or current.quote_volume is None:
                return None
            previous_close = history[index - 1].close
            prior_ranges = [_true_range_at(history, i) for i in range(index - 24, index)]
            prior_volumes = _mean_quote_volume(history[index - 24:index])
            if prior_volumes is None or prior_volumes <= 0:
                return None
            negative_return = current.close / previous_close - 1.0
            normalized_range = fmean(prior_ranges) / previous_close
            if negative_return <= -shock_multiple * normalized_range and current.quote_volume >= 2.0 * prior_volumes:
                return SignalDecision("BUY", "exp006_capitulation_entry")
            return None

        return high_volume_shock_reversal

    raise ValueError(f"unknown experiment strategy: {experiment_id}")

def run_buy_and_hold(bars: Sequence[Bar], *, initial_capital: float, costs: CostModel,
                     constraints: QuantityConstraints) -> BacktestResult:
    data = _run_inputs(bars, initial_capital, costs, constraints)
    initial, cash, qty = float(initial_capital), float(initial_capital), 0.0
    entry = None
    fills, rejected, trades, curve = [], [], [], []
    for i, bar in enumerate(data):
        if i == 0:
            fill, detail = _buy(cash, float(bar.open), bar.session, None, "benchmark", costs, constraints)
            if fill is None:
                rejected.append(RejectedOrder("BUY", "benchmark", None, bar.session, detail or "rejected"))
            else:
                cash -= fill.quantity * fill.fill_price + fill.commission
                if cash < 0 and cash > -1e-7:
                    cash = 0.0
                qty, entry = fill.quantity, fill
                fills.append(fill)
        if i == len(data) - 1 and qty > 0 and entry is not None:
            fill, detail = _sell(qty, entry, float(bar.close), bar.close_time or bar.session, None, "end_of_test", costs, constraints)
            if fill is None:
                rejected.append(RejectedOrder("SELL", "end_of_test", None, bar.session, detail or "rejected"))
            else:
                cash += qty * fill.fill_price - fill.commission
                trades.append(_trade(entry, fill))
                fills.append(fill)
                qty, entry = 0.0, None
        curve.append(EquityPoint(bar.session, cash, qty, cash + qty * float(bar.close)))
    return _result(initial, cash, qty, fills, rejected, trades, curve)


def compute_window_metrics(result: BacktestResult, *, start_session: date, end_session: date) -> WindowMetrics:
    if start_session > end_session:
        raise ValueError("window start must not follow end")
    start_dt = datetime.combine(start_session, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(end_session + timedelta(days=1), time.min, tzinfo=timezone.utc)

    def in_window(timestamp: str) -> bool:
        value = _bar_datetime(timestamp)
        return start_dt <= value < end_exclusive

    points = [p for p in result.equity_curve if in_window(p.session)]
    if not points:
        raise ValueError("window has no equity points")
    prior = [p for p in result.equity_curve if _bar_datetime(p.session) < start_dt]
    start_equity = prior[-1].equity if prior else result.initial_capital
    final_equity = points[-1].equity
    peak, drawdown = start_equity, 0.0
    for point in points:
        peak = max(peak, point.equity)
        if peak > 0:
            drawdown = max(drawdown, (peak - point.equity) / peak)
    trades = [t for t in result.trades if in_window(t.exit.fill_session)]
    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [t.net_pnl for t in trades if t.net_pnl < 0]
    fills = [f for f in result.fills if in_window(f.fill_session)]
    return WindowMetrics(
        start_session.isoformat(), end_session.isoformat(), start_equity, final_equity,
        100 * (final_equity / start_equity - 1), 100 * drawdown, len(trades),
        fsum(wins) / abs(fsum(losses)) if losses else None,
        fmean(t.net_pnl for t in trades) if trades else None,
        100 * len(wins) / len(trades) if trades else None,
        100 * sum(p.quantity > 0 for p in points) / len(points),
        fsum(_fill_cost(f) for f in fills),
    )


WINDOWS = {
    "development": (date(2018, 1, 1), date(2021, 12, 31)),
    "validation": (date(2022, 1, 1), date(2023, 12, 31)),
    "final_test": (date(2024, 1, 1), date(2025, 12, 31)),
    "full_period": (date(2018, 1, 1), date(2025, 12, 31)),
}
BASE_COSTS = CostModel(10, 2, 3)
STRESS_COSTS = CostModel(20, 4, 6)


def run_exp001(dataset_dir: str | Path, *, initial_capital: float = 10_000.0) -> dict:
    root = Path(dataset_dir)
    data = load_binance_vision_klines(root)
    constraints = load_binance_quantity_constraints(root / "exchange_filters_snapshot.json")
    scenarios = {"base": BASE_COSTS, "stress_double_all_costs": STRESS_COSTS}
    output = {
        "experiment_id": "EXP-001",
        "instrument": "BTCUSDT Spot",
        "timeframe": "1d UTC",
        "period": "2018-01-01 through 2025-12-31",
        "engine_sha256": _sha256_file(Path(__file__)),
        "data": {
            "source": "Binance Vision Spot monthly klines",
            "archive_count": data.archive_count,
            "rows": len(data.bars),
            "milliseconds_rows": data.milliseconds_rows,
            "microseconds_rows": data.microseconds_rows,
            "download_manifest_sha256": data.manifest_sha256,
        },
        "strategy": {
            "rule": "SMA20/SMA100 crossover, long-only",
            "signal": "closed daily bar",
            "execution": "next daily open; terminal close if filters permit",
            "initial_capital_usdt": initial_capital,
            "quantity_constraints": asdict(constraints),
        },
        "cost_scenarios_bps": {name: asdict(model) for name, model in scenarios.items()},
        "windows": {},
    }
    for scenario, costs in scenarios.items():
        strategy = run_backtest(data.bars, initial_capital=initial_capital, costs=costs, constraints=constraints)
        benchmark = run_buy_and_hold(data.bars, initial_capital=initial_capital, costs=costs, constraints=constraints)
        output["windows"][scenario] = {}
        for name, (start, end) in WINDOWS.items():
            output["windows"][scenario][name] = {
                "strategy": asdict(compute_window_metrics(strategy, start_session=start, end_session=end)),
                "benchmark_buy_and_hold": asdict(compute_window_metrics(benchmark, start_session=start, end_session=end)),
            }
        output["windows"][scenario]["diagnostics"] = {
            "strategy_fills": len(strategy.fills),
            "strategy_rejected_orders": [asdict(x) for x in strategy.rejected_orders],
            "strategy_completed_trades": len(strategy.trades),
            "strategy_open_quantity_at_end": strategy.equity_curve[-1].quantity,
            "strategy_total_costs_usdt": strategy.total_costs,
            "strategy_final_equity_usdt": strategy.final_capital,
            "benchmark_fills": len(benchmark.fills),
            "benchmark_rejected_orders": [asdict(x) for x in benchmark.rejected_orders],
            "benchmark_total_costs_usdt": benchmark.total_costs,
            "benchmark_final_equity_usdt": benchmark.final_capital,
        }
    return output



EXP003_WINDOWS = {
    "development": (date(2018, 1, 1), date(2021, 12, 31)),
    "validation": (date(2022, 1, 1), date(2023, 12, 31)),
}
EXP003_CONFIGS = {
    "EXP-002": (
        {"config_id": "D20_10", "entry_lookback": 20, "exit_lookback": 10},
        {"config_id": "D55_20", "entry_lookback": 55, "exit_lookback": 20},
        {"config_id": "D100_40", "entry_lookback": 100, "exit_lookback": 40},
    ),
    "EXP-003": (
        {"config_id": "R2_05", "rsi_period": 2, "entry_threshold": 5, "exit_threshold": 50, "maximum_held_bars": 10},
        {"config_id": "R2_10", "rsi_period": 2, "entry_threshold": 10, "exit_threshold": 50, "maximum_held_bars": 10},
        {"config_id": "R3_10", "rsi_period": 3, "entry_threshold": 10, "exit_threshold": 50, "maximum_held_bars": 10},
    ),
    "EXP-004": (
        {"config_id": "V1_3", "shock_multiple": 1.0, "maximum_held_bars": 3},
        {"config_id": "V1_5", "shock_multiple": 1.5, "maximum_held_bars": 5},
        {"config_id": "V2_10", "shock_multiple": 2.0, "maximum_held_bars": 10},
    ),
}
EXP003_COSTS = {"base": BASE_COSTS, "stress_double_all_costs": STRESS_COSTS}


def _result_diagnostics(result: BacktestResult) -> dict:
    return {
        "fill_count": len(result.fills),
        "rejected_orders": [asdict(item) for item in result.rejected_orders],
        "completed_trades": len(result.trades),
        "open_quantity_at_end": result.equity_curve[-1].quantity,
        "total_costs_usdt": result.total_costs,
        "final_equity_usdt": result.final_capital,
    }


def run_trl003(dataset_dir: str | Path, *, initial_capital: float = 10_000.0) -> dict:
    root = Path(dataset_dir)
    loaded = load_binance_vision_klines(
        root, start_session=date(2018, 1, 1), end_session=date(2023, 12, 31)
    )
    constraints = load_binance_quantity_constraints(root / "exchange_filters_snapshot.json")
    all_bars = loaded.bars
    dev_start, dev_end = EXP003_WINDOWS["development"]
    val_start, val_end = EXP003_WINDOWS["validation"]
    dev_bars = tuple(bar for bar in all_bars if dev_start.isoformat() <= bar.session <= dev_end.isoformat())
    val_bars = tuple(bar for bar in all_bars if val_start.isoformat() <= bar.session <= val_end.isoformat())
    if len(dev_bars) != 1461 or len(val_bars) != 730:
        raise ValueError("TRL-003 windows do not match the frozen daily calendar")

    benchmarks = {}
    for window_name, bars, bounds in (
        ("development", dev_bars, EXP003_WINDOWS["development"]),
        ("validation", val_bars, EXP003_WINDOWS["validation"]),
    ):
        benchmarks[window_name] = {}
        for scenario, costs in EXP003_COSTS.items():
            benchmark = run_buy_and_hold(bars, initial_capital=initial_capital, costs=costs, constraints=constraints)
            metrics = compute_window_metrics(benchmark, start_session=bounds[0], end_session=bounds[1])
            benchmarks[window_name][scenario] = {
                "metrics": asdict(metrics),
                "diagnostics": _result_diagnostics(benchmark),
            }

    experiments = {}
    for experiment_id, configurations in EXP003_CONFIGS.items():
        attempted = []
        for configuration in configurations:
            policy = make_exp_strategy_policy(experiment_id, configuration)
            item = {"config_id": configuration["config_id"], "parameters": configuration.copy(), "development": {}}
            for scenario, costs in EXP003_COSTS.items():
                result = run_backtest(
                    dev_bars, initial_capital=initial_capital, costs=costs, constraints=constraints,
                    signal_policy=policy,
                )
                metrics = compute_window_metrics(result, start_session=dev_start, end_session=dev_end)
                item["development"][scenario] = {
                    "metrics": asdict(metrics),
                    "diagnostics": _result_diagnostics(result),
                }
            attempted.append(item)

        selected = sorted(
            attempted,
            key=lambda item: (
                -item["development"]["base"]["metrics"]["net_return_pct"],
                item["development"]["base"]["metrics"]["max_drawdown_pct"],
                item["config_id"],
            ),
        )[0]
        selected_policy = make_exp_strategy_policy(experiment_id, selected["parameters"])
        validation = {}
        for scenario, costs in EXP003_COSTS.items():
            result = run_backtest(
                val_bars, initial_capital=initial_capital, costs=costs, constraints=constraints,
                signal_policy=selected_policy, signal_history=dev_bars,
            )
            metrics = compute_window_metrics(result, start_session=val_start, end_session=val_end)
            validation[scenario] = {
                "metrics": asdict(metrics),
                "diagnostics": _result_diagnostics(result),
            }

        base_metrics = validation["base"]["metrics"]
        stress_metrics = validation["stress_double_all_costs"]["metrics"]
        base_benchmark = benchmarks["validation"]["base"]["metrics"]
        stress_benchmark = benchmarks["validation"]["stress_double_all_costs"]["metrics"]
        gates = {
            "at_least_30_completed_trades_in_both_cost_scenarios": (
                base_metrics["trade_count"] >= 30 and stress_metrics["trade_count"] >= 30
            ),
            "base_profit_factor_gt_1": base_metrics["profit_factor"] is not None and base_metrics["profit_factor"] > 1,
            "base_net_return_positive": base_metrics["net_return_pct"] > 0,
            "doubled_cost_net_return_positive": stress_metrics["net_return_pct"] > 0,
            "drawdown_below_benchmark_in_both_cost_scenarios": (
                base_metrics["max_drawdown_pct"] < base_benchmark["max_drawdown_pct"]
                and stress_metrics["max_drawdown_pct"] < stress_benchmark["max_drawdown_pct"]
            ),
        }
        if not gates["at_least_30_completed_trades_in_both_cost_scenarios"]:
            classification = "INCONCLUSIVE"
        elif all(gates.values()):
            classification = "CANDIDATA preliminare"
        else:
            classification = "SCARTATA"
        experiments[experiment_id] = {
            "selected_config_id": selected["config_id"],
            "selection_rule": "highest development base-cost net return; tie: lower maximum drawdown, then config_id",
            "attempted_configurations": attempted,
            "validation_selected_configuration": validation,
            "validation_gates": gates,
            "classification": classification,
        }

    return {
        "order": "TRL-003",
        "experiments": experiments,
        "protocol": {
            "instrument": "BTCUSDT Spot",
            "timeframe": "1d UTC",
            "loaded_period": "2018-01-01 through 2023-12-31",
            "windows": {name: [start.isoformat(), end.isoformat()] for name, (start, end) in EXP003_WINDOWS.items()},
            "initial_capital_usdt_per_window": initial_capital,
            "quantity_constraints": asdict(constraints),
            "cost_scenarios_bps": {name: asdict(model) for name, model in EXP003_COSTS.items()},
            "research_parameter_configurations": sum(len(items) for items in EXP003_CONFIGS.values()),
            "development_scenario_evaluations": sum(len(items) for items in EXP003_CONFIGS.values()) * len(EXP003_COSTS),
            "validation_selected_scenario_evaluations": len(EXP003_CONFIGS) * len(EXP003_COSTS),
            "final_test_opened": False,
            "paper_trading_started": False,
        },
        "data": {
            "source": "Binance Vision Spot monthly klines",
            "archive_count_loaded": loaded.archive_count,
            "rows_loaded": len(all_bars),
            "download_manifest_sha256": loaded.manifest_sha256,
        },
        "engine_sha256": _sha256_file(Path(__file__)),
        "benchmarks": benchmarks,
    }


TRL004_WINDOWS = {
    "development_2018_2021": (date(2018, 1, 1), date(2021, 12, 31), 1461),
    "validation_2022_2023": (date(2022, 1, 1), date(2023, 12, 31), 730),
    "extension_2024_2025": (date(2024, 1, 1), date(2025, 12, 31), 731),
}
TRL004_STRATEGIES = {
    "EXP-002": {"config_id": "D20_10", "parameters": {"entry_lookback": 20, "exit_lookback": 10}},
    "EXP-004": {"config_id": "V2_10", "parameters": {"shock_multiple": 2.0, "maximum_held_bars": 10}},
}
TRL004_COSTS = {"base": BASE_COSTS, "stress_double_all_costs": STRESS_COSTS}


def _linear_quantile(sorted_values: Sequence[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _trade_distribution(result: BacktestResult) -> dict:
    values = sorted(trade.net_pnl for trade in result.trades)
    winners = sorted((value for value in values if value > 0), reverse=True)
    positive_total = fsum(winners)
    return {
        "trade_count": len(values),
        "winner_count": len(winners),
        "loser_count": sum(value < 0 for value in values),
        "zero_pnl_count": sum(value == 0 for value in values),
        "mean_net_pnl_usdt": fsum(values) / len(values) if values else None,
        "median_net_pnl_usdt": _linear_quantile(values, 0.5),
        "p05_net_pnl_usdt": _linear_quantile(values, 0.05),
        "p95_net_pnl_usdt": _linear_quantile(values, 0.95),
        "best_net_trade_usdt": max(values) if values else None,
        "worst_net_trade_usdt": min(values) if values else None,
        "positive_trade_pnl_total_usdt": positive_total if winners else None,
        "top_1_winner_share_pct": 100 * winners[0] / positive_total if positive_total else None,
        "top_3_winner_share_pct": 100 * fsum(winners[:3]) / positive_total if positive_total else None,
    }


def run_trl004(dataset_dir: str | Path, *, initial_capital: float = 10_000.0) -> dict:
    root = Path(dataset_dir)
    loaded = load_binance_vision_klines(
        root, start_session=date(2018, 1, 1), end_session=date(2025, 12, 31), symbol="ETHUSDT"
    )
    snapshot_path = root / "exchange_filters_snapshot.json"
    constraints = load_binance_quantity_constraints(snapshot_path, symbol="ETHUSDT")
    all_bars = loaded.bars
    windows = {}
    for window_id, (start, end, expected_count) in TRL004_WINDOWS.items():
        window_bars = tuple(bar for bar in all_bars if start.isoformat() <= bar.session <= end.isoformat())
        if len(window_bars) != expected_count:
            raise ValueError(f"TRL-004 calendar mismatch for {window_id}")
        history = tuple(bar for bar in all_bars if bar.session < start.isoformat())
        windows[window_id] = {"start": start, "end": end, "bars": window_bars, "history": history}

    benchmarks = {}
    for window_id, window in windows.items():
        benchmarks[window_id] = {}
        for scenario, costs in TRL004_COSTS.items():
            result = run_buy_and_hold(
                window["bars"], initial_capital=initial_capital, costs=costs, constraints=constraints
            )
            metrics = compute_window_metrics(
                result, start_session=window["start"], end_session=window["end"]
            )
            benchmarks[window_id][scenario] = {
                "metrics": asdict(metrics),
                "diagnostics": _result_diagnostics(result),
            }

    experiments = {}
    for experiment_id, frozen in TRL004_STRATEGIES.items():
        policy = make_exp_strategy_policy(experiment_id, frozen["parameters"])
        experiment = {"config_id": frozen["config_id"], "windows": {}}
        for window_id, window in windows.items():
            cost_results = {}
            for scenario, costs in TRL004_COSTS.items():
                result = run_backtest(
                    window["bars"], initial_capital=initial_capital, costs=costs,
                    constraints=constraints, signal_policy=policy, signal_history=window["history"],
                )
                metrics = compute_window_metrics(
                    result, start_session=window["start"], end_session=window["end"]
                )
                benchmark_metrics = benchmarks[window_id][scenario]["metrics"]
                cost_results[scenario] = {
                    "metrics": asdict(metrics),
                    "return_difference_vs_buy_and_hold_pp": metrics.net_return_pct - benchmark_metrics["net_return_pct"],
                    "benchmark_metrics": benchmark_metrics,
                    "diagnostics": _result_diagnostics(result),
                    "trade_distribution": _trade_distribution(result),
                    "trade_records": [asdict(trade) for trade in result.trades],
                }
            base = cost_results["base"]["metrics"]
            stress = cost_results["stress_double_all_costs"]["metrics"]
            base_benchmark = benchmarks[window_id]["base"]["metrics"]
            stress_benchmark = benchmarks[window_id]["stress_double_all_costs"]["metrics"]
            gates = {
                "at_least_30_completed_trades_in_both_cost_scenarios": (
                    base["trade_count"] >= 30 and stress["trade_count"] >= 30
                ),
                "positive_net_return_in_both_cost_scenarios": (
                    base["net_return_pct"] > 0 and stress["net_return_pct"] > 0
                ),
                "profit_factor_gt_1_in_both_cost_scenarios": (
                    base["profit_factor"] is not None and base["profit_factor"] > 1
                    and stress["profit_factor"] is not None and stress["profit_factor"] > 1
                ),
                "drawdown_below_benchmark_in_both_cost_scenarios": (
                    base["max_drawdown_pct"] < base_benchmark["max_drawdown_pct"]
                    and stress["max_drawdown_pct"] < stress_benchmark["max_drawdown_pct"]
                ),
            }
            if not gates["at_least_30_completed_trades_in_both_cost_scenarios"]:
                classification = "INCONCLUSIVE"
            elif all(gates.values()):
                classification = "PRELIMINARY_HISTORICALLY_FAVORABLE"
            else:
                classification = "DOES_NOT_PASS_ECONOMIC_CHECK"
            experiment["windows"][window_id] = {
                "base_and_stress": cost_results,
                "interpretation_gates": gates,
                "classification": classification,
            }
        experiments[experiment_id] = experiment

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    return {
        "order": "TRL-004",
        "instrument": "ETHUSDT Spot",
        "timeframe": "1d UTC",
        "experiments": experiments,
        "protocol": {
            "loaded_period": "2018-01-01 through 2025-12-31",
            "windows": {
                name: {"start": start.isoformat(), "end": end.isoformat(), "rows": count}
                for name, (start, end, count) in TRL004_WINDOWS.items()
            },
            "initial_capital_usdt_per_window": initial_capital,
            "quantity_constraints": asdict(constraints),
            "cost_scenarios_bps": {name: asdict(model) for name, model in TRL004_COSTS.items()},
            "strategies_and_configs": {name: {"config_id": item["config_id"], "parameters": item["parameters"]}
                                       for name, item in TRL004_STRATEGIES.items()},
            "strategy_window_scenario_runs": len(TRL004_STRATEGIES) * len(TRL004_WINDOWS) * len(TRL004_COSTS),
            "benchmark_window_scenario_runs": len(TRL004_WINDOWS) * len(TRL004_COSTS),
            "aggregate_return": None,
            "aggregate_note": "Not calculated: each window starts with separately reset capital, so returns are reported per window.",
            "paper_trading_started": False,
        },
        "data": {
            "source": "Binance Vision Spot monthly klines",
            "symbol": "ETHUSDT",
            "archive_count_loaded": loaded.archive_count,
            "rows_loaded": len(all_bars),
            "milliseconds_rows": loaded.milliseconds_rows,
            "microseconds_rows": loaded.microseconds_rows,
            "download_manifest_sha256": loaded.manifest_sha256,
            "exchange_info_snapshot_sha256": _sha256_file(snapshot_path),
            "exchange_info_retrieved_utc": snapshot.get("retrieved_utc"),
        },
        "engine_sha256": _sha256_file(Path(__file__)),
        "benchmarks": benchmarks,
    }

TRL005_WINDOWS = {
    "development": (date(2018, 1, 1), date(2021, 12, 31), 8766),
    "validation": (date(2022, 1, 1), date(2023, 12, 31), 4380),
}
TRL005_STRATEGIES = {
    "EXP-005": {
        "title": "Volatility-compression breakout continuation",
        "configs": (
            {"config_id": "C12", "parameters": {"breakout_lookback": 12}},
            {"config_id": "C24", "parameters": {"breakout_lookback": 24}},
        ),
    },
    "EXP-006": {
        "title": "High-volume negative-shock reversal",
        "configs": (
            {"config_id": "S20", "parameters": {"shock_multiple": 2.0}},
            {"config_id": "S25", "parameters": {"shock_multiple": 2.5}},
        ),
    },
}
TRL005_COSTS = {"base": BASE_COSTS, "stress_double_all_costs": STRESS_COSTS}


def _trade_duration_summary(result: BacktestResult) -> dict:
    hours = []
    bars = []
    for trade in result.trades:
        start = _bar_datetime(trade.entry.fill_session)
        end = _bar_datetime(trade.exit.fill_session)
        duration_hours = max(0.0, (end - start).total_seconds() / 3600)
        hours.append(duration_hours)
        bars.append(int(round(duration_hours / 4)))
    if not bars:
        return {
            "trade_count": 0, "min_bars": None, "median_bars": None, "mean_bars": None, "max_bars": None,
            "min_hours": None, "median_hours": None, "mean_hours": None, "max_hours": None,
        }
    sorted_bars, sorted_hours = sorted(bars), sorted(hours)
    return {
        "trade_count": len(bars),
        "min_bars": min(bars),
        "median_bars": _linear_quantile(sorted_bars, 0.5),
        "mean_bars": fsum(bars) / len(bars),
        "max_bars": max(bars),
        "min_hours": min(hours),
        "median_hours": _linear_quantile(sorted_hours, 0.5),
        "mean_hours": fsum(hours) / len(hours),
        "max_hours": max(hours),
    }


def _trl005_run_record(result: BacktestResult, metrics: WindowMetrics) -> dict:
    return {
        "metrics": asdict(metrics),
        "diagnostics": _result_diagnostics(result),
        "trade_distribution": _trade_distribution(result),
        "trade_duration": _trade_duration_summary(result),
        "trade_records": [asdict(trade) for trade in result.trades],
    }


def _trl005_cash_reference(initial_capital: float) -> dict:
    return {
        "initial_capital_usdt": initial_capital,
        "final_equity_usdt": initial_capital,
        "net_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "total_costs_usdt": 0.0,
        "trade_count": 0,
    }


def _trl005_development_gates(base_metrics: dict, stress_metrics: dict, benchmark_base: dict) -> dict:
    gates = {
        "at_least_30_completed_trades_in_both_cost_scenarios": (
            base_metrics["trade_count"] >= 30 and stress_metrics["trade_count"] >= 30
        ),
        "positive_net_return_in_both_cost_scenarios": (
            base_metrics["net_return_pct"] > 0 and stress_metrics["net_return_pct"] > 0
        ),
        "base_profit_factor_gt_1": (
            base_metrics["profit_factor"] is not None and base_metrics["profit_factor"] > 1
        ),
        "base_drawdown_below_base_buy_and_hold": (
            base_metrics["max_drawdown_pct"] < benchmark_base["max_drawdown_pct"]
        ),
    }
    gates["eligible_for_validation"] = all(gates.values())
    return gates


def _trl005_choose_development_config(configurations: dict, benchmark_base: dict) -> tuple[str | None, dict]:
    eligible = []
    gate_results = {}
    for config_id, configuration in configurations.items():
        base = configuration["cost_scenarios"]["base"]["metrics"]
        stress = configuration["cost_scenarios"]["stress_double_all_costs"]["metrics"]
        gates = _trl005_development_gates(base, stress, benchmark_base)
        gate_results[config_id] = gates
        if gates["eligible_for_validation"]:
            eligible.append(config_id)
    if not eligible:
        return None, {"eligible_config_ids": [], "selected_config_id": None, "reason": "no configuration passed all predeclared development gates", "gates_by_config": gate_results}
    selected = sorted(
        eligible,
        key=lambda config_id: (
            -configurations[config_id]["cost_scenarios"]["stress_double_all_costs"]["metrics"]["net_return_pct"],
            configurations[config_id]["cost_scenarios"]["stress_double_all_costs"]["metrics"]["max_drawdown_pct"],
            config_id,
        ),
    )[0]
    return selected, {
        "eligible_config_ids": eligible,
        "selected_config_id": selected,
        "reason": "highest stress-cost net return; ties resolved by lower stress drawdown, then config ID",
        "gates_by_config": gate_results,
    }


def run_trl005_development(dataset_dir: str | Path, *, initial_capital: float = 10_000.0) -> dict:
    root = Path(dataset_dir)
    start, end, expected_rows = TRL005_WINDOWS["development"]
    loaded = load_binance_vision_klines(
        root, start_session=start, end_session=end, symbol="BTCUSDT", interval="4h"
    )
    if len(loaded.bars) != expected_rows:
        raise ValueError("TRL-005 development calendar count mismatch")
    constraints_path = root.parent / "1d" / "exchange_filters_snapshot.json"
    constraints = load_binance_quantity_constraints(constraints_path, symbol="BTCUSDT")
    benchmarks = {}
    for scenario, costs in TRL005_COSTS.items():
        result = run_buy_and_hold(loaded.bars, initial_capital=initial_capital, costs=costs, constraints=constraints)
        metrics = compute_window_metrics(result, start_session=start, end_session=end)
        benchmarks[scenario] = {"metrics": asdict(metrics), "diagnostics": _result_diagnostics(result)}

    experiments = {}
    selected_for_validation = []
    for experiment_id, spec in TRL005_STRATEGIES.items():
        configurations = {}
        for frozen in spec["configs"]:
            config_id = frozen["config_id"]
            policy = make_exp_strategy_policy(experiment_id, frozen["parameters"])
            cost_scenarios = {}
            for scenario, costs in TRL005_COSTS.items():
                result = run_backtest(
                    loaded.bars, initial_capital=initial_capital, costs=costs,
                    constraints=constraints, signal_policy=policy,
                )
                metrics = compute_window_metrics(result, start_session=start, end_session=end)
                cost_scenarios[scenario] = _trl005_run_record(result, metrics)
            configurations[config_id] = {
                "parameters": frozen["parameters"],
                "cost_scenarios": cost_scenarios,
            }
        selected, decision = _trl005_choose_development_config(
            configurations, benchmarks["base"]["metrics"]
        )
        if selected is not None:
            selected_for_validation.append({"experiment_id": experiment_id, "config_id": selected})
        experiments[experiment_id] = {
            "title": spec["title"],
            "configurations": configurations,
            "development_selection": decision,
        }

    return {
        "order": "TRL-005",
        "phase": "development",
        "market": "BTCUSDT Spot",
        "interval": "4h UTC",
        "data": {
            "source": "Binance Vision Spot monthly klines",
            "symbol": "BTCUSDT",
            "interval": "4h",
            "period": "2018-01-01 through 2021-12-31",
            "archive_count_loaded": loaded.archive_count,
            "rows_loaded": len(loaded.bars),
            "milliseconds_rows": loaded.milliseconds_rows,
            "microseconds_rows": loaded.microseconds_rows,
            "download_manifest_sha256": loaded.manifest_sha256,
        },
        "initial_capital_usdt": initial_capital,
        "quantity_constraints": asdict(constraints),
        "cost_scenarios_bps": {name: asdict(model) for name, model in TRL005_COSTS.items()},
        "configuration_count_tested": sum(len(item["configs"]) for item in TRL005_STRATEGIES.values()),
        "strategy_runs": 8,
        "benchmark_runs": 2,
        "benchmarks": benchmarks,
        "cash_reference": _trl005_cash_reference(initial_capital),
        "experiments": experiments,
        "selected_for_validation": selected_for_validation,
        "validation_opened": False,
        "final_test_opened": False,
        "paper_trading_started": False,
        "engine_sha256": _sha256_file(Path(__file__)),
    }


def _trl005_recompute_selected(development: dict) -> list[dict]:
    if development.get("order") != "TRL-005" or development.get("phase") != "development":
        raise ValueError("validation requires a TRL-005 development result")
    benchmark_base = development["benchmarks"]["base"]["metrics"]
    selected = []
    for experiment_id, experiment in development["experiments"].items():
        choice, decision = _trl005_choose_development_config(
            experiment["configurations"], benchmark_base
        )
        if decision != experiment["development_selection"]:
            raise ValueError(f"development selection record does not reconcile for {experiment_id}")
        if choice is not None:
            selected.append({"experiment_id": experiment_id, "config_id": choice})
    if selected != development.get("selected_for_validation"):
        raise ValueError("development selected-config list does not reconcile")
    return selected


def _trl005_validation_gates(base_metrics: dict, stress_metrics: dict, benchmark_base: dict, benchmark_stress: dict) -> dict:
    gates = {
        "at_least_30_completed_trades_in_both_cost_scenarios": (
            base_metrics["trade_count"] >= 30 and stress_metrics["trade_count"] >= 30
        ),
        "positive_net_return_in_both_cost_scenarios": (
            base_metrics["net_return_pct"] > 0 and stress_metrics["net_return_pct"] > 0
        ),
        "profit_factor_gt_1_in_both_cost_scenarios": (
            base_metrics["profit_factor"] is not None and base_metrics["profit_factor"] > 1
            and stress_metrics["profit_factor"] is not None and stress_metrics["profit_factor"] > 1
        ),
        "drawdown_below_buy_and_hold_in_both_cost_scenarios": (
            base_metrics["max_drawdown_pct"] < benchmark_base["max_drawdown_pct"]
            and stress_metrics["max_drawdown_pct"] < benchmark_stress["max_drawdown_pct"]
        ),
    }
    if not gates["at_least_30_completed_trades_in_both_cost_scenarios"]:
        classification = "INCONCLUSIVE"
    elif all(gates.values()):
        classification = "PRELIMINARY_HISTORICALLY_FAVORABLE"
    else:
        classification = "SCARTATA"
    return {"gates": gates, "classification": classification}


def run_trl005_validation(
    dataset_dir: str | Path, development_result_path: str | Path, *, initial_capital: float = 10_000.0
) -> dict:
    development_path = Path(development_result_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    selected = _trl005_recompute_selected(development)
    output = {
        "order": "TRL-005",
        "phase": "validation",
        "market": "BTCUSDT Spot",
        "interval": "4h UTC",
        "development_result_sha256": _sha256_file(development_path),
        "selected_for_validation": selected,
        "validation_opened": bool(selected),
        "final_test_opened": False,
        "paper_trading_started": False,
        "cash_reference": _trl005_cash_reference(initial_capital),
        "engine_sha256": _sha256_file(Path(__file__)),
    }
    if not selected:
        output.update({"data": None, "benchmarks": {}, "experiments": {}, "benchmark_runs": 0, "strategy_runs": 0})
        return output

    root = Path(dataset_dir)
    start, end, expected_rows = TRL005_WINDOWS["validation"]
    loaded = load_binance_vision_klines(
        root, start_session=date(2018, 1, 1), end_session=end, symbol="BTCUSDT", interval="4h"
    )
    all_bars = loaded.bars
    history = tuple(bar for bar in all_bars if bar.session[:10] < start.isoformat())
    validation_bars = tuple(bar for bar in all_bars if start.isoformat() <= bar.session[:10] <= end.isoformat())
    if len(history) != TRL005_WINDOWS["development"][2] or len(validation_bars) != expected_rows:
        raise ValueError("TRL-005 validation/warm-up calendar count mismatch")
    constraints_path = root.parent / "1d" / "exchange_filters_snapshot.json"
    constraints = load_binance_quantity_constraints(constraints_path, symbol="BTCUSDT")

    benchmarks = {}
    for scenario, costs in TRL005_COSTS.items():
        result = run_buy_and_hold(validation_bars, initial_capital=initial_capital, costs=costs, constraints=constraints)
        metrics = compute_window_metrics(result, start_session=start, end_session=end)
        benchmarks[scenario] = {"metrics": asdict(metrics), "diagnostics": _result_diagnostics(result)}

    experiments = {}
    for item in selected:
        experiment_id, config_id = item["experiment_id"], item["config_id"]
        frozen = next(c for c in TRL005_STRATEGIES[experiment_id]["configs"] if c["config_id"] == config_id)
        policy = make_exp_strategy_policy(experiment_id, frozen["parameters"])
        cost_scenarios = {}
        for scenario, costs in TRL005_COSTS.items():
            result = run_backtest(
                validation_bars, initial_capital=initial_capital, costs=costs,
                constraints=constraints, signal_policy=policy, signal_history=history,
            )
            metrics = compute_window_metrics(result, start_session=start, end_session=end)
            cost_scenarios[scenario] = _trl005_run_record(result, metrics)
        decision = _trl005_validation_gates(
            cost_scenarios["base"]["metrics"],
            cost_scenarios["stress_double_all_costs"]["metrics"],
            benchmarks["base"]["metrics"],
            benchmarks["stress_double_all_costs"]["metrics"],
        )
        for scenario, record in cost_scenarios.items():
            record["return_difference_vs_buy_and_hold_pp"] = (
                record["metrics"]["net_return_pct"] - benchmarks[scenario]["metrics"]["net_return_pct"]
            )
            record["return_difference_vs_cash_pp"] = record["metrics"]["net_return_pct"]
        experiments[experiment_id] = {
            "config_id": config_id,
            "parameters": frozen["parameters"],
            "cost_scenarios": cost_scenarios,
            "validation_decision": decision,
        }

    output.update({
        "data": {
            "source": "Binance Vision Spot monthly klines",
            "symbol": "BTCUSDT",
            "interval": "4h",
            "loaded_period_for_causal_warmup": "2018-01-01 through 2023-12-31",
            "archive_count_loaded": loaded.archive_count,
            "rows_loaded": len(all_bars),
            "development_warmup_rows": len(history),
            "validation_rows": len(validation_bars),
            "milliseconds_rows": loaded.milliseconds_rows,
            "microseconds_rows": loaded.microseconds_rows,
            "download_manifest_sha256": loaded.manifest_sha256,
        },
        "initial_capital_usdt": initial_capital,
        "quantity_constraints": asdict(constraints),
        "cost_scenarios_bps": {name: asdict(model) for name, model in TRL005_COSTS.items()},
        "benchmarks": benchmarks,
        "benchmark_runs": 2,
        "strategy_runs": 2 * len(selected),
        "experiments": experiments,
    })
    return output


def run_trl005(
    dataset_dir: str | Path, *, phase: str = "development", development_result_path: str | Path | None = None,
    initial_capital: float = 10_000.0,
) -> dict:
    if phase == "development":
        return run_trl005_development(dataset_dir, initial_capital=initial_capital)
    if phase == "validation":
        if development_result_path is None:
            raise ValueError("validation phase requires --development-results")
        return run_trl005_validation(
            dataset_dir, development_result_path, initial_capital=initial_capital
        )
    raise ValueError("TRL-005 phase must be development or validation")


def main():
    parser = argparse.ArgumentParser(description="Run deterministic BTCUSDT daily and frozen H4 research with the existing engine.")
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--experiment", choices=("EXP-001", "TRL-003", "TRL-004", "TRL-005"), default="EXP-001")
    parser.add_argument("--phase", choices=("development", "validation"), default="development")
    parser.add_argument("--development-results")
    args = parser.parse_args()
    if args.experiment == "EXP-001":
        if args.phase != "development" or args.development_results:
            parser.error("--phase and --development-results apply only to TRL-005")
        result = run_exp001(args.dataset_dir)
    elif args.experiment == "TRL-003":
        if args.phase != "development" or args.development_results:
            parser.error("--phase and --development-results apply only to TRL-005")
        result = run_trl003(args.dataset_dir)
    elif args.experiment == "TRL-004":
        if args.phase != "development" or args.development_results:
            parser.error("--phase and --development-results apply only to TRL-005")
        result = run_trl004(args.dataset_dir)
    else:
        result = run_trl005(
            args.dataset_dir, phase=args.phase, development_result_path=args.development_results
        )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved local {args.experiment} results to {output_path}")


if __name__ == "__main__":
    main()
