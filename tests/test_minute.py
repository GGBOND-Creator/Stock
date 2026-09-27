from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_model.minute import MINUTE_COLUMNS, normalize_baostock_minutes, update_minute_archive


def source_frame(rows: list[list[str]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["date", "time", "code", "open", "high", "low", "close", "volume", "amount", "adjustflag"],
    )


class MinuteArchiveTests(unittest.TestCase):
    def test_normalizes_baostock_bar_end_timestamp(self) -> None:
        frame = source_frame(
            [["2026-08-14", "20260814093500000", "sz.002714", "40", "40.2", "39.9", "40.1", "100", "4000", "3"]]
        )
        normalized = normalize_baostock_minutes(frame)
        self.assertEqual(list(normalized.columns), MINUTE_COLUMNS)
        self.assertEqual(str(normalized.iloc[0]["datetime"]), "2026-08-14 09:35:00+08:00")
        self.assertEqual(normalized.iloc[0]["close"], 40.1)

    def test_incremental_update_replaces_overlap_and_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "5m.csv"
            first = normalize_baostock_minutes(
                source_frame(
                    [
                        ["2026-08-14", "20260814093500000", "sz.002714", "40", "40.2", "39.9", "40.1", "100", "4000", "3"],
                        ["2026-08-14", "20260814094000000", "sz.002714", "40.1", "40.3", "40", "40.2", "120", "4800", "3"],
                    ]
                )
            )
            update_minute_archive(
                first,
                output,
                symbol="002714.SZ",
                source="test",
                frequency_minutes=5,
                adjustment="none",
                volume_unit="unknown",
                amount_unit="unknown",
                requested_start="2026-08-14",
                requested_end="2026-08-14",
            )

            second = normalize_baostock_minutes(
                source_frame(
                    [
                        ["2026-08-14", "20260814094000000", "sz.002714", "40.1", "40.4", "40", "40.3", "125", "5000", "3"],
                        ["2026-08-14", "20260814094500000", "sz.002714", "40.3", "40.5", "40.2", "40.4", "130", "5200", "3"],
                    ]
                )
            )
            result = update_minute_archive(
                second,
                output,
                symbol="002714.SZ",
                source="test",
                frequency_minutes=5,
                adjustment="none",
                volume_unit="unknown",
                amount_unit="unknown",
                requested_start="2026-08-14",
                requested_end="2026-08-14",
            )

            archived = pd.read_csv(output)
            self.assertEqual(len(archived), 3)
            self.assertEqual(archived.loc[archived["datetime"] == "2026-08-14T09:40:00+08:00", "close"].iloc[0], 40.3)
            self.assertEqual(result.duplicate_timestamps_replaced, 1)
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], "ohlcv_minute_v1")
            self.assertEqual(metadata["timestamp_meaning"], "bar_end")
            self.assertEqual(metadata["output_rows"], 3)
            self.assertEqual(metadata["initial_requested_start"], "2026-08-14")
            self.assertEqual(len(metadata["output_sha256"]), 64)

    def test_rejects_invalid_price_relationship(self) -> None:
        frame = source_frame(
            [["2026-08-14", "20260814093500000", "sz.002714", "40", "39", "38", "40.1", "100", "4000", "3"]]
        )
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            normalize_baostock_minutes(frame)

    def test_rejects_update_with_different_adjustment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "5m.csv"
            fetched = normalize_baostock_minutes(
                source_frame(
                    [["2026-08-14", "20260814093500000", "sz.002714", "40", "40.2", "39.9", "40.1", "100", "4000", "3"]]
                )
            )
            common = {
                "symbol": "002714.SZ",
                "source": "test",
                "frequency_minutes": 5,
                "volume_unit": "unknown",
                "amount_unit": "unknown",
                "requested_start": "2026-08-14",
                "requested_end": "2026-08-14",
            }
            update_minute_archive(fetched, output, adjustment="none", **common)
            with self.assertRaisesRegex(ValueError, "contract does not match"):
                update_minute_archive(fetched, output, adjustment="qfq", **common)


if __name__ == "__main__":
    unittest.main()
