from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.a_share import (
    fetch_akshare_history,
    fetch_baostock_history,
    save_frame,
    to_project_symbol,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch A-share daily OHLCV history.")
    parser.add_argument("symbol", help="Stock symbol, for example: 000001.SZ or 600519.SH.")
    parser.add_argument("--source", choices=["akshare", "baostock"], default="akshare", help="Free data source.")
    parser.add_argument("--start", default="20180101", help="Start date. AkShare: YYYYMMDD; BaoStock: YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="End date. AkShare: YYYYMMDD; BaoStock: YYYY-MM-DD.")
    parser.add_argument("--adjust", default="qfq", help="AkShare adjust: qfq, hfq, or empty string.")
    parser.add_argument("--adjustflag", default="2", help="BaoStock adjustflag: 1 back, 2 front, 3 none.")
    parser.add_argument("--output-dir", default="data/raw", help="Output directory for normalized OHLCV CSV.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = to_project_symbol(args.symbol)
    if args.source == "akshare":
        frame = fetch_akshare_history(symbol, start=args.start, end=args.end, adjust=args.adjust)
    else:
        frame = fetch_baostock_history(symbol, start=args.start, end=args.end, adjustflag=args.adjustflag)

    output = Path(args.output_dir) / f"{symbol}.csv"
    output_path = save_frame(frame, output)
    print(frame.tail(10).to_string(index=False))
    print(f"Rows: {len(frame)}")
    print(f"Saved A-share history: {output_path}")


if __name__ == "__main__":
    main()
