from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.converter import CANONICAL_COLUMNS, convert_market_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an external market CSV/TXT file to canonical OHLCV.")
    parser.add_argument("--input", required=True, help="External CSV/TXT file.")
    parser.add_argument("--output", required=True, help="Canonical CSV output path.")
    parser.add_argument("--source", required=True, help="Human-readable data source name.")
    parser.add_argument("--symbol", required=True, help="Project symbol, for example 000001.SZ.")
    parser.add_argument("--market", default="unknown", help="Market name, for example A-share.")
    parser.add_argument("--frequency", default="1d", help="Bar frequency. The current model expects 1d.")
    parser.add_argument("--adjustment", default="unknown", help="Price adjustment: qfq, hfq, none, or unknown.")
    parser.add_argument("--volume-unit", default="source_native", help="Volume unit, for example shares or lots.")
    parser.add_argument("--date-format", default=None, help="Optional datetime format, for example %%Y%%m%%d.")
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="TARGET=SOURCE",
        help="Explicit column mapping. Repeat as needed, for example --map date=交易日期.",
    )
    parser.add_argument(
        "--drop-invalid",
        action="store_true",
        help="Drop invalid OHLCV relationship rows instead of stopping.",
    )
    return parser.parse_args()


def parse_mapping(values: list[str]) -> dict[str, str]:
    mapping = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --map value {value!r}; expected TARGET=SOURCE")
        target, source = (part.strip() for part in value.split("=", 1))
        if target not in CANONICAL_COLUMNS:
            raise ValueError(f"Unknown target {target!r}; expected one of {CANONICAL_COLUMNS}")
        if not source:
            raise ValueError(f"Source column is empty in --map value {value!r}")
        mapping[target] = source
    return mapping


def main() -> None:
    args = parse_args()
    result = convert_market_csv(
        args.input,
        args.output,
        source=args.source,
        symbol=args.symbol,
        market=args.market,
        frequency=args.frequency,
        adjustment=args.adjustment,
        volume_unit=args.volume_unit,
        column_mapping=parse_mapping(args.map),
        date_format=args.date_format,
        strict=not args.drop_invalid,
    )
    print(f"Converted {result.output_rows}/{result.input_rows} rows -> {result.output_path}")
    print(f"Audit metadata -> {result.metadata_path}")
    if result.dropped_rows:
        print(f"Review required: dropped {result.dropped_rows} rows.")


if __name__ == "__main__":
    main()
