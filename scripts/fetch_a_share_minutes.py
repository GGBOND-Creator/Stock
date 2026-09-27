from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.a_share import to_project_symbol
from stock_model.minute import fetch_baostock_minutes, load_minute_archive, update_minute_archive


ADJUSTMENT_NAMES = {"1": "hfq", "2": "qfq", "3": "none"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and incrementally archive BaoStock A-share minute bars.")
    parser.add_argument("symbol", help="Stock symbol, for example: 002714.SZ.")
    parser.add_argument("--frequency", type=int, choices=[5, 15, 30, 60], default=5, help="Bar size in minutes.")
    parser.add_argument("--start", default=None, help="Explicit start date, YYYY-MM-DD.")
    parser.add_argument(
        "--initial-start",
        default="2024-01-01",
        help="Start date used only when the archive does not exist.",
    )
    parser.add_argument("--end", default=None, help="End date, YYYY-MM-DD; defaults to today.")
    parser.add_argument(
        "--adjustflag",
        choices=["1", "2", "3"],
        default="3",
        help="BaoStock adjustment: 1 back, 2 front, 3 none. Raw archives default to none.",
    )
    parser.add_argument("--output", default=None, help="Archive CSV path.")
    parser.add_argument("--volume-unit", default="unknown", help="Documented source volume unit, or unknown.")
    parser.add_argument("--amount-unit", default="unknown", help="Documented source amount unit, or unknown.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = to_project_symbol(args.symbol)
    output = Path(args.output or f"data/minute/{symbol}/{args.frequency}m_baostock.csv")
    end = args.end or date.today().isoformat()

    if args.start:
        start = args.start
    elif output.is_file():
        archive = load_minute_archive(output)
        start = archive["datetime"].max().date().isoformat()
    else:
        start = args.initial_start

    if start > end:
        raise SystemExit(f"Start date {start} is after end date {end}.")

    fetched = fetch_baostock_minutes(
        symbol,
        start=start,
        end=end,
        frequency_minutes=args.frequency,
        adjustflag=args.adjustflag,
    )
    result = update_minute_archive(
        fetched,
        output,
        symbol=symbol,
        source="BaoStock query_history_k_data_plus",
        frequency_minutes=args.frequency,
        adjustment=ADJUSTMENT_NAMES[args.adjustflag],
        volume_unit=args.volume_unit,
        amount_unit=args.amount_unit,
        requested_start=start,
        requested_end=end,
    )
    print(
        f"Fetched {result.fetched_rows} rows; archive {result.previous_rows} -> {result.output_rows} rows; "
        f"replaced {result.duplicate_timestamps_replaced} overlapping timestamps."
    )
    print(f"Trading days: {result.trading_days}")
    print(f"Minute archive: {result.output_path}")
    print(f"Audit metadata: {result.metadata_path}")


if __name__ == "__main__":
    main()
