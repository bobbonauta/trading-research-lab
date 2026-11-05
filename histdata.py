"""Minimal HistData EURUSD M1 reader and complete UTC candle aggregation.

This module does not implement FX order execution or a Forex backtest model.
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

EST_FIXED = timezone(-timedelta(hours=5), name="EST")
UTC = timezone.utc


@dataclass(frozen=True)
class HistDataBar:
    """A provider M1 Bid bar, timestamped at its open in UTC.

    The source's Volume field is deliberately not retained as market volume.
    """

    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


def parse_histdata_m1_row(row: Sequence[str], *, source: str = "HistData") -> HistDataBar:
    """Parse one six-field Generic ASCII row using fixed EST (UTC-05:00)."""
    if len(row) != 6:
        raise ValueError(f"{source}: expected 6 semicolon-separated fields, found {len(row)}")
    fields = [field.strip() for field in row]
    try:
        source_time = datetime.strptime(fields[0], "%Y%m%d %H%M%S")
    except ValueError as exc:
        raise ValueError(f"{source}: invalid EST timestamp") from exc
    if source_time.strftime("%Y%m%d %H%M%S") != fields[0] or source_time.second != 0:
        raise ValueError(f"{source}: timestamp must be a canonical minute boundary")

    try:
        open_price, high, low, close = (Decimal(value) for value in fields[1:5])
        reported_volume = Decimal(fields[5])
    except InvalidOperation as exc:
        raise ValueError(f"{source}: malformed numeric field") from exc
    prices = (open_price, high, low, close)
    if any(not value.is_finite() or value <= 0 for value in prices):
        raise ValueError(f"{source}: OHLC prices must be finite and positive")
    if high < max(open_price, close) or low > min(open_price, close) or high < low:
        raise ValueError(f"{source}: inconsistent OHLC values")
    if not reported_volume.is_finite() or reported_volume < 0:
        raise ValueError(f"{source}: invalid provider Volume field")

    timestamp_utc = source_time.replace(tzinfo=EST_FIXED).astimezone(UTC)
    return HistDataBar(timestamp_utc, open_price, high, low, close)


def load_histdata_m1_month_from_zip(
    archive_path: str | Path, *, year: int, month: int
) -> tuple[HistDataBar, ...]:
    """Read only the requested original-EST month from an annual HistData ZIP."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if year < 1 or year > 9999:
        raise ValueError("year must be a four-digit calendar year")

    expected_csv = f"DAT_ASCII_EURUSD_M1_{year:04d}.csv"
    bars: list[HistDataBar] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if csv_names != [expected_csv]:
                raise ValueError(f"expected exactly one annual CSV named {expected_csv}")
            prefix = f"{year:04d}{month:02d}"
            with archive.open(expected_csv, "r") as binary:
                reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""), delimiter=";")
                for row_number, row in enumerate(reader, 1):
                    if not row or not row[0].strip().startswith(prefix):
                        continue
                    bar = parse_histdata_m1_row(row, source=f"{expected_csv}:{row_number}")
                    if bars and bar.timestamp_utc <= bars[-1].timestamp_utc:
                        raise ValueError("HistData M1 timestamps must be strictly increasing and unique")
                    bars.append(bar)
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        raise ValueError(f"cannot read HistData archive: {archive_path}") from exc
    if not bars:
        raise ValueError(f"archive contains no rows for {year:04d}-{month:02d} EST")
    return tuple(bars)


def _validate_bar(bar: HistDataBar) -> datetime:
    if not isinstance(bar, HistDataBar):
        raise ValueError("all input values must be HistDataBar instances")
    timestamp = bar.timestamp_utc
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError("bar timestamp must be timezone-aware UTC")
    timestamp = timestamp.astimezone(UTC)
    if timestamp.second or timestamp.microsecond:
        raise ValueError("M1 bar timestamp must be aligned to a whole minute")
    prices = (bar.open, bar.high, bar.low, bar.close)
    if any(not isinstance(value, Decimal) or not value.is_finite() or value <= 0 for value in prices):
        raise ValueError("bar OHLC prices must be finite positive Decimal values")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close) or bar.high < bar.low:
        raise ValueError("bar has inconsistent OHLC values")
    return timestamp


def aggregate_histdata_m1(
    bars: Sequence[HistDataBar], *, hours: int
) -> tuple[HistDataBar, ...]:
    """Aggregate complete H1 or H4 UTC buckets; omit gaps and partial buckets.

    Returned timestamps are candle opens. They do not define order fill times.
    """
    if hours not in (1, 4):
        raise ValueError("hours must be 1 or 4")
    buckets: dict[datetime, list[HistDataBar]] = {}
    previous: datetime | None = None
    for bar in bars:
        timestamp = _validate_bar(bar)
        if previous is not None and timestamp <= previous:
            raise ValueError("M1 timestamps must be strictly increasing and unique")
        previous = timestamp
        bucket_hour = timestamp.hour // hours * hours
        bucket_start = timestamp.replace(hour=bucket_hour, minute=0)
        buckets.setdefault(bucket_start, []).append(bar)

    result: list[HistDataBar] = []
    expected_minutes = hours * 60
    for bucket_start, members in buckets.items():
        if len(members) != expected_minutes:
            continue
        if any(
            member.timestamp_utc.astimezone(UTC) != bucket_start + timedelta(minutes=index)
            for index, member in enumerate(members)
        ):
            continue
        result.append(
            HistDataBar(
                bucket_start,
                members[0].open,
                max(member.high for member in members),
                min(member.low for member in members),
                members[-1].close,
            )
        )
    return tuple(result)
