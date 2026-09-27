from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import load_network_tables
from stock_model.network_signals import (
    build_signal_snapshot,
    load_signal_store,
    network_objects_and_edges,
    write_signal_snapshot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an as-of network signal field without future leakage.")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--signal-dir", default="data/network_signals/a_share")
    parser.add_argument("--output", default="data/processed/network_signal_snapshot/signal_state_snapshot.csv")
    args = parser.parse_args()
    tables = load_network_tables(args.network_dir)
    store = load_signal_store(args.signal_dir)
    objects, edges = network_objects_and_edges(tables)
    snapshot = build_signal_snapshot(
        store.events,
        store.rules,
        edges,
        as_of=args.as_of,
        signal_types=store.signal_types,
        objects=objects,
    )
    write_signal_snapshot(snapshot, args.output)
    print(f"Objects: {len(objects)}")
    print(f"Signal rows: {len(snapshot)}")
    print(f"Non-zero rows: {(snapshot['concentration'].abs() > 0).sum()}")
    print(f"Saved snapshot: {args.output}")


if __name__ == "__main__":
    main()
