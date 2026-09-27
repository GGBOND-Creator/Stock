from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.a_share import fetch_akshare_spot, save_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch current A-share market snapshot with AkShare.")
    parser.add_argument("--output", default="data/realtime/a_share_spot.csv", help="CSV output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = fetch_akshare_spot()
    output_path = save_frame(frame, args.output)
    print(frame.head(20).to_string(index=False))
    print(f"Rows: {len(frame)}")
    print(f"Saved A-share spot snapshot: {output_path}")


if __name__ == "__main__":
    main()
