from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import load_network_tables
from stock_model.network_signals import (
    SignalStore,
    lifecycle_status_observations_to_signal_events,
    load_signal_store,
    merge_lifecycle_status_signals,
    validate_signal_events,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import fetch-time listing-status observations as direct lifecycle signals."
    )
    parser.add_argument("--event-id", action="append", required=True)
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--signal-dir", default="data/network_signals/a_share")
    args = parser.parse_args()

    network = load_network_tables(args.network_dir)
    store = load_signal_store(args.signal_dir)
    incoming = lifecycle_status_observations_to_signal_events(
        network.lifecycle_events, event_ids=args.event_id
    )
    merged = merge_lifecycle_status_signals(store.events, incoming)
    validate_signal_events(merged, store.signal_types)

    signal_dir = Path(args.signal_dir)
    merged.to_csv(signal_dir / "signal_events.csv", index=False, encoding="utf-8-sig")
    meta_path = signal_dir / "signal_store.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    metadata.update(
        {
            "schema_version": "network_signal_field_v1",
            "signal_event_rows": int(len(merged)),
            "signal_evidence_rows": int(len(store.evidence)),
            "transmission_rule_rows": int(len(store.rules)),
            "last_import": {
                "method": "fetch_time_lifecycle_status_observation",
                "source_event_ids": args.event_id,
            },
        }
    )
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported lifecycle signals: {len(incoming)}")
    print(f"Signal events after idempotent merge: {len(merged)}")
    print("Propagation rules added: 0")
    print(f"Saved: {signal_dir / 'signal_events.csv'}")


if __name__ == "__main__":
    main()
