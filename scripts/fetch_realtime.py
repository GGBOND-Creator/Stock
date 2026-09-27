from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.realtime import RealtimeConfig, fetch_realtime_quotes, save_realtime_quotes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch realtime quotes from local TongHuaShun/iFinD.")
    parser.add_argument("symbols", nargs="+", help="Stock symbols, for example: 000001.SZ 600519.SH")
    parser.add_argument(
        "--indicators",
        default="open,high,low,latest,volume,amount",
        help="Comma-separated THS_RQ indicators.",
    )
    parser.add_argument("--params", default="", help="Optional THS_RQ parameter string.")
    parser.add_argument("--ifind-path", default=None, help="Directory containing iFinDPy. Or set IFINDPY_PATH.")
    parser.add_argument("--username", default=None, help="TongHuaShun/iFinD username. Or set THS_USERNAME.")
    parser.add_argument("--password", default=None, help="TongHuaShun/iFinD password. Or set THS_PASSWORD.")
    parser.add_argument("--no-login", action="store_true", help="Skip THS_iFinDLogin before THS_RQ.")
    parser.add_argument("--output", default="data/realtime/latest_quotes.csv", help="CSV output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    indicators = [item.strip() for item in args.indicators.split(",") if item.strip()]
    config = RealtimeConfig(
        provider="ifind",
        username=args.username,
        password=args.password,
        ifind_path=args.ifind_path,
        params=args.params,
        login=not args.no_login,
    )
    try:
        frame = fetch_realtime_quotes(args.symbols, indicators=indicators, config=config)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(frame.to_string(index=False))
    output_path = save_realtime_quotes(frame, args.output)
    print(f"Saved realtime quotes: {output_path}")


if __name__ == "__main__":
    main()
