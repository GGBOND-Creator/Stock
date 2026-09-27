from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (
    build_network_snapshot,
    load_network_tables,
    write_network_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an as-of A-share industry network without future event leakage."
    )
    parser.add_argument("--as-of", required=True, help="Knowledge cutoff, preferably ISO-8601.")
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--output-dir", default="data/processed/industry_network_snapshot")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include snapshot-only active candidates. Keep off for verified research universes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tables = load_network_tables(args.network_dir)
    snapshot = build_network_snapshot(
        tables, as_of=args.as_of, include_unverified=args.include_unverified
    )
    write_network_snapshot(snapshot, args.output_dir)
    print(f"Companies in registry: {len(snapshot.companies)}")
    print(f"Companies in network: {int(snapshot.companies['network_included'].sum())}")
    print(f"Listings in network: {int(snapshot.listings['network_included'].sum())}")
    print(f"Active industry memberships: {int(snapshot.memberships['network_active'].sum())}")
    print(f"Pending known lifecycle events: {len(snapshot.pending_events)}")
    print(f"Market impact events: {len(snapshot.market_impacts)}")
    print(f"Saved snapshot: {args.output_dir}")


if __name__ == "__main__":
    main()
