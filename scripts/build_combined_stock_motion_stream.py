from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import load_network_tables
from stock_model.motion import (
    build_motion_metadata,
    build_network_motion_stream,
    convert_ohlcv_file,
    merge_motion_streams,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one internal motion stream from market OHLCV plus reviewed "
            "industry-network evidence."
        )
    )
    parser.add_argument("--input", required=True, help="Canonical daily OHLCV CSV.")
    parser.add_argument("--output", required=True, help="Combined motion CSV.")
    parser.add_argument(
        "--network-dir", default="data/industry_network/a_share"
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--source", default=None)
    parser.add_argument("--market", default=None)
    parser.add_argument("--adjustment", default=None)
    parser.add_argument("--volume-unit", default=None)
    parser.add_argument("--source-meta", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    market_stream, market_meta, _market_output_meta = convert_ohlcv_file(
        args.input,
        args.output,
        symbol=args.symbol,
        source=args.source,
        market=args.market,
        adjustment=args.adjustment,
        volume_unit=args.volume_unit,
        source_metadata_path=args.source_meta,
    )
    tables = load_network_tables(args.network_dir)
    network_stream = build_network_motion_stream(tables, symbol=args.symbol)
    combined = merge_motion_streams(market_stream, network_stream)
    output_path = Path(args.output)
    combined.to_csv(output_path, index=False)
    metadata = build_motion_metadata(
        combined,
        input_path=Path(args.input),
        output_path=output_path,
        symbol=args.symbol,
        source=market_meta["source"],
        market=market_meta["market"],
        adjustment=market_meta["adjustment"],
        volume_unit=market_meta["volume_unit"],
        source_metadata_path=(
            Path(market_meta["source_metadata_file"])
            if market_meta.get("source_metadata_file")
            else None
        ),
        input_schema="ohlcv_daily_v1+a_share_industry_network_v2",
        additional_input_files=[str(Path(args.network_dir).resolve())],
    )
    metadata["market_event_rows"] = int(len(market_stream))
    metadata["network_event_rows"] = int(len(network_stream))
    metadata["network_channels"] = sorted(network_stream["channel"].unique().tolist())
    metadata["network_evidence_policy"] = (
        "approved product mappings are observations; anonymous counterparty concentration is proxy only"
    )
    metadata["network_time_semantics"] = {
        "approved_activity_event_time": (
            "source observation time because the business effective date is not disclosed"
        ),
        "approved_activity_available_time": "human review completion time",
        "annual_report_event_time": "report period end",
        "annual_report_available_time": "verified local first-ingestion time",
    }
    metadata["warnings"].append(
        "A reviewed business description confirms a disclosed activity role, not production volume, capacity, profitability, or a fixed valuation range."
    )
    audit_path = Path(f"{output_path}.meta.json")
    audit_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Market motion events: {len(market_stream)}")
    print(f"Network motion events: {len(network_stream)}")
    print(f"Combined motion events: {len(combined)}")
    print(f"Saved combined motion stream: {output_path}")
    print(f"Saved audit metadata: {audit_path}")


if __name__ == "__main__":
    main()
