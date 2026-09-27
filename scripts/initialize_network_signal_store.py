from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.network_signals import initialize_signal_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the evidence-gated network signal store.")
    parser.add_argument("--output-dir", default="data/network_signals/a_share")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    store = initialize_signal_store(args.output_dir, overwrite=args.overwrite)
    print(f"Signal types: {len(store.signal_types)}")
    print(f"Events: {len(store.events)}")
    print(f"Event evidence: {len(store.evidence)}")
    print(f"Transmission rules: {len(store.rules)}")
    print(f"Saved signal store: {args.output_dir}")


if __name__ == "__main__":
    main()
