from __future__ import annotations

import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from histdata import (
    HistDataBar,
    aggregate_histdata_m1,
    load_histdata_m1_month_from_zip,
    parse_histdata_m1_row,
)


def _bars(start: datetime, count: int, *, omit: set[int] | None = None) -> list[HistDataBar]:
    omit = omit or set()
    bars = []
    for index in range(count):
        if index in omit:
            continue
        price = Decimal("1.100000") + Decimal(index) * Decimal("0.000001")
        bars.append(
            HistDataBar(
                start + timedelta(minutes=index),
                price,
                price + Decimal("0.000002"),
                price - Decimal("0.000002"),
                price + Decimal("0.000001"),
            )
        )
    return bars


class HistDataTests(unittest.TestCase):
    def test_fixed_est_to_utc_including_next_day_and_dst_date(self):
        midnight = parse_histdata_m1_row(["20200101 000000", "1", "1", "1", "1", "0"])
        next_day = parse_histdata_m1_row(["20200101 193000", "1", "1", "1", "1", "0"])
        dst_date = parse_histdata_m1_row(["20200308 033000", "1", "1", "1", "1", "0"])
        self.assertEqual(midnight.timestamp_utc, datetime(2020, 1, 1, 5, tzinfo=timezone.utc))
        self.assertEqual(next_day.timestamp_utc, datetime(2020, 1, 2, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(dst_date.timestamp_utc, datetime(2020, 3, 8, 8, 30, tzinfo=timezone.utc))

    def test_parser_rejects_wrong_schema_and_noncanonical_timestamp(self):
        with self.assertRaisesRegex(ValueError, "expected 6"):
            parse_histdata_m1_row(["20200101 000000", "1", "1", "1", "1"])
        with self.assertRaisesRegex(ValueError, "timestamp"):
            parse_histdata_m1_row(["20200101 000001", "1", "1", "1", "1", "0"])

    def test_parser_rejects_nonpositive_nonfinite_and_malformed_prices(self):
        rows = (
            ["20200101 000000", "0", "1", "1", "1", "0"],
            ["20200101 000000", "NaN", "1", "1", "1", "0"],
            ["20200101 000000", "bad", "1", "1", "1", "0"],
        )
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_histdata_m1_row(row)

    def test_parser_rejects_inconsistent_ohlc_and_invalid_provider_volume(self):
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            parse_histdata_m1_row(["20200101 000000", "1.2", "1.1", "1.0", "1.2", "0"])
        with self.assertRaisesRegex(ValueError, "Volume"):
            parse_histdata_m1_row(["20200101 000000", "1", "1", "1", "1", "-1"])

    def test_source_volume_is_not_retained_as_market_volume(self):
        bar = parse_histdata_m1_row(["20200101 000000", "1", "1", "1", "1", "0"])
        self.assertFalse(hasattr(bar, "volume"))
        self.assertFalse(hasattr(bar, "quote_volume"))

    def test_h1_and_h4_are_aligned_to_utc_and_use_full_ohlc(self):
        start = datetime(2020, 1, 1, 0, tzinfo=timezone.utc)
        bars = _bars(start, 240)
        h1 = aggregate_histdata_m1(bars, hours=1)
        h4 = aggregate_histdata_m1(bars, hours=4)
        self.assertEqual(len(h1), 4)
        self.assertEqual([bar.timestamp_utc.hour for bar in h1], [0, 1, 2, 3])
        self.assertEqual(len(h4), 1)
        self.assertEqual(h4[0].timestamp_utc, start)
        self.assertEqual(h4[0].open, bars[0].open)
        self.assertEqual(h4[0].high, max(bar.high for bar in bars))
        self.assertEqual(h4[0].low, min(bar.low for bar in bars))
        self.assertEqual(h4[0].close, bars[-1].close)

    def test_incomplete_utc_buckets_are_omitted_and_gaps_do_not_shift_buckets(self):
        start = datetime(2020, 1, 1, 0, tzinfo=timezone.utc)
        bars = _bars(start, 120, omit={30})
        h1 = aggregate_histdata_m1(bars, hours=1)
        self.assertEqual(len(h1), 1)
        self.assertEqual(h1[0].timestamp_utc, start + timedelta(hours=1))
        self.assertEqual(aggregate_histdata_m1(_bars(start, 239), hours=4), ())

        partial_edges = _bars(start + timedelta(hours=2), 480)
        h4 = aggregate_histdata_m1(partial_edges, hours=4)
        self.assertEqual(len(h4), 1)
        self.assertEqual(h4[0].timestamp_utc, start + timedelta(hours=4))

    def test_aggregation_rejects_unsupported_interval_duplicate_and_unsorted_inputs(self):
        start = datetime(2020, 1, 1, 0, tzinfo=timezone.utc)
        bars = _bars(start, 3)
        with self.assertRaisesRegex(ValueError, "hours"):
            aggregate_histdata_m1(bars, hours=2)
        with self.assertRaisesRegex(ValueError, "increasing"):
            aggregate_histdata_m1([bars[0], bars[0]], hours=1)
        with self.assertRaisesRegex(ValueError, "increasing"):
            aggregate_histdata_m1([bars[1], bars[0]], hours=1)

    def test_zip_month_loader_filters_and_reads_repeatably(self):
        rows = "\n".join(
            (
                "20200101 000000;1.1;1.2;1.0;1.15;0",
                "20200101 000100;1.15;1.2;1.1;1.18;0",
                "20200201 000000;9;9;9;9;0",
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "sample.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("DAT_ASCII_EURUSD_M1_2020.csv", rows)
                archive.writestr("DAT_ASCII_EURUSD_M1_2020.txt", "sample status")
            first = load_histdata_m1_month_from_zip(archive_path, year=2020, month=1)
            second = load_histdata_m1_month_from_zip(archive_path, year=2020, month=1)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0].timestamp_utc, datetime(2020, 1, 1, 5, tzinfo=timezone.utc))

    def test_zip_month_loader_rejects_empty_month_and_invalid_month(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "sample.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("DAT_ASCII_EURUSD_M1_2020.csv", "20200201 000000;1;1;1;1;0")
            with self.assertRaisesRegex(ValueError, "no rows"):
                load_histdata_m1_month_from_zip(archive_path, year=2020, month=1)
            with self.assertRaisesRegex(ValueError, "month"):
                load_histdata_m1_month_from_zip(archive_path, year=2020, month=13)


if __name__ == "__main__":
    unittest.main()
