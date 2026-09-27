from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_model.converter import convert_market_csv


class ConverterTests(unittest.TestCase):
    def test_converts_chinese_columns_units_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.csv"
            output = root / "normalized.csv"
            source.write_text(
                "日期,开盘价,最高价,最低价,收盘价,成交量(手)\n"
                "2024-01-02,10,12,9,11,1.2万\n"
                "2024-01-02,10,13,9,12,2万\n"
                "2024-01-03,12,12.5,11,11.5,8000\n",
                encoding="utf-8-sig",
            )

            result = convert_market_csv(
                source,
                output,
                source="unit-test",
                symbol="TEST.SZ",
                market="A-share",
                adjustment="qfq",
                volume_unit="lots",
            )

            converted = pd.read_csv(output)
            self.assertEqual(list(converted.columns), ["date", "open", "high", "low", "close", "volume"])
            self.assertEqual(len(converted), 2)
            self.assertEqual(converted.iloc[0]["close"], 12)
            self.assertEqual(converted.iloc[0]["volume"], 20000)
            self.assertEqual(result.duplicate_dates, 1)

            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], "ohlcv_daily_v1")
            self.assertEqual(metadata["symbol"], "TEST.SZ")
            self.assertEqual(metadata["output_rows"], 2)
            self.assertEqual(len(metadata["input_sha256"]), 64)

    def test_strict_mode_rejects_impossible_price_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "invalid.csv"
            source.write_text(
                "date,open,high,low,close,volume\n2024-01-02,10,9,8,11,100\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid OHLCV"):
                convert_market_csv(source, root / "out.csv", source="test", symbol="TEST")

    def test_explicit_column_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "custom.csv"
            output = root / "out.csv"
            source.write_text(
                "day,o,h,l,c,v\n20240102,10,11,9,10.5,1000\n",
                encoding="utf-8",
            )
            result = convert_market_csv(
                source,
                output,
                source="custom",
                symbol="TEST",
                column_mapping={"date": "day", "open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"},
                date_format="%Y%m%d",
            )
            self.assertEqual(result.output_rows, 1)
            self.assertEqual(pd.read_csv(output).iloc[0]["date"], "2024-01-02")

    def test_rejects_non_daily_frequency_before_losing_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "minute.csv"
            source.write_text(
                "date,open,high,low,close,volume\n2024-01-02 09:31,10,11,9,10.5,1000\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Only daily bars"):
                convert_market_csv(
                    source,
                    root / "out.csv",
                    source="test",
                    symbol="TEST",
                    frequency="1m",
                )


if __name__ == "__main__":
    unittest.main()
