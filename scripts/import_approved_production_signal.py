from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import load_network_tables
from stock_model.network_signals import (
    approved_production_mappings_to_signal_bundle,
    load_signal_store,
    merge_signal_evidence,
    merge_signal_events,
    validate_signal_events,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import reviewed producer mappings as direct production-activity signals."
    )
    parser.add_argument("--mapping-id", action="append", required=True)
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--signal-dir", default="data/network_signals/a_share")
    args = parser.parse_args()

    network = load_network_tables(args.network_dir)
    store = load_signal_store(args.signal_dir)
    incoming_events, incoming_evidence = approved_production_mappings_to_signal_bundle(
        network.business_activities,
        network.products,
        network.activity_product_candidates,
        mapping_ids=args.mapping_id,
    )
    events = merge_signal_events(store.events, incoming_events)
    evidence, events = merge_signal_evidence(store.evidence, incoming_evidence, events)
    validate_signal_events(events, store.signal_types)

    signal_dir = Path(args.signal_dir)
    events.to_csv(signal_dir / "signal_events.csv", index=False, encoding="utf-8-sig")
    evidence.to_csv(
        signal_dir / "signal_event_evidence.csv", index=False, encoding="utf-8-sig"
    )
    meta_path = signal_dir / "signal_store.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "signal_event_rows": int(len(events)),
            "signal_evidence_rows": int(len(evidence)),
            "transmission_rule_rows": int(len(store.rules)),
            "last_production_import": {
                "method": "approved_exact_text_product_mapping",
                "source_mapping_ids": args.mapping_id,
                "raw_numeric_value": None,
                "raw_unit": "not_reported",
                "display_strength": 1.0,
            },
            "known_limits": [
                "production activity presence is confirmed, but production quantity is not reported",
                "official A-share list presence confirms listing presence, not continuous trading availability",
                "no signal propagates without both an explicit network edge and transmission rule",
                "display colours and normalized strengths are encodings, not measured value",
            ],
        }
    )
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Imported production signals: {len(incoming_events)}")
    print(f"Signal events after idempotent merge: {len(events)}")
    print(f"Signal evidence rows: {len(evidence)}")
    print("Raw production quantity: not reported")
    print("Propagation rules added: 0")


if __name__ == "__main__":
    main()
