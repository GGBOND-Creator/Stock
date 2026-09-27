from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.network_signal_view import (
    build_signal_report_model,
    write_signal_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a read-only network-signal report from project CSV tables."
    )
    parser.add_argument("--symbol", required=True, help="Canonical listing symbol.")
    parser.add_argument(
        "--snapshot",
        default="data/processed/network_signal_snapshot/signal_state_snapshot.csv",
    )
    parser.add_argument("--signal-dir", default="data/network_signals/a_share")
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument(
        "--output", default="reports/network_signal_inspector.html"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot_path = Path(args.snapshot)
    signal_dir = Path(args.signal_dir)
    network_dir = Path(args.network_dir)
    input_paths = [
        snapshot_path,
        signal_dir / "signal_types.csv",
        signal_dir / "signal_events.csv",
        signal_dir / "signal_event_evidence.csv",
        signal_dir / "transmission_rules.csv",
        network_dir / "companies.csv",
        network_dir / "listings.csv",
        network_dir / "products.csv",
        network_dir / "activity_product_candidates.csv",
    ]
    frames = [pd.read_csv(path, dtype=str) for path in input_paths]
    model = build_signal_report_model(
        symbol=args.symbol,
        snapshot=frames[0],
        signal_types=frames[1],
        events=frames[2],
        evidence=frames[3],
        rules=frames[4],
        companies=frames[5],
        listings=frames[6],
        products=frames[7],
        mappings=frames[8],
    )
    output, metadata = write_signal_report(
        args.output, model, input_paths=input_paths
    )
    print(f"Non-zero signals: {model['nonzero_signal_count']}")
    print(f"Transmission rules at snapshot: {model['transmission_rule_count']}")
    print(f"Later verification evidence: {model['later_evidence_count']}")
    print(f"Saved report: {output}")
    print(f"Saved audit metadata: {metadata}")


if __name__ == "__main__":
    main()
