from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.ths import import_ths_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import TongHuaShun exported CSV/TXT files.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Single 同花顺 exported CSV/TXT file.")
    source.add_argument("--directory", help="Directory containing 同花顺 exported CSV/TXT files.")
    parser.add_argument("--pattern", default="*.csv", help="File pattern used with --directory.")
    parser.add_argument("--symbol", default=None, help="Symbol for single-file import. Defaults to input stem.")
    parser.add_argument("--output-dir", default="data/raw", help="Directory for normalized OHLCV CSV files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.input:
        output_path = import_ths_export(args.input, symbol=args.symbol, output_dir=args.output_dir)
        print(f"Imported: {args.input} -> {output_path}")
        return

    directory = Path(args.directory)
    paths = sorted(path for path in directory.glob(args.pattern) if path.is_file())
    if not paths:
        raise FileNotFoundError(f"No files matched: {directory / args.pattern}")

    for path in paths:
        output_path = import_ths_export(path, output_dir=args.output_dir)
        print(f"Imported: {path} -> {output_path}")


if __name__ == "__main__":
    main()
