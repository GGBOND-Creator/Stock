from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.network_signals import (
    load_signal_store,
    merge_signal_evidence,
    szse_a_share_list_evidence,
    validate_signal_events,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SZSE_REPORT_URL = "https://www.szse.cn/api/report/ShowReport/data"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-check a lifecycle signal against the official SZSE A-share list."
    )
    parser.add_argument("--signal-event-id", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--signal-dir", default="data/network_signals/a_share")
    parser.add_argument(
        "--archive-root",
        default="data/external/a_share_industry_network/szse",
    )
    args = parser.parse_args()

    fetched_at = pd.Timestamp.now(tz="UTC")
    params = {
        "SHOWTYPE": "JSON",
        "CATALOGID": "1110",
        "TABKEY": "tab1",
        "txtDMorJC": args.symbol,
    }
    response = requests.get(
        SZSE_REPORT_URL,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    raw_bytes = response.content

    archive_dir = Path(args.archive_root) / fetched_at.strftime("%Y%m%dT%H%M%SZ")
    archive_dir.mkdir(parents=True, exist_ok=True)
    response_path = archive_dir / f"{args.symbol}_a_share_list.json"
    response_path.write_bytes(raw_bytes)
    relative_response = response_path.resolve().relative_to(PROJECT_ROOT.resolve())
    query_meta = {
        "fetched_at_utc": fetched_at.isoformat(),
        "source": "Shenzhen Stock Exchange official A-share list",
        "request_url": response.url,
        "http_status": response.status_code,
        "response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "symbol": args.symbol,
        "expected_name": args.expected_name,
    }
    (archive_dir / "query.meta.json").write_text(
        json.dumps(query_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    store = load_signal_store(args.signal_dir)
    if args.signal_event_id not in set(store.events["signal_event_id"].astype(str)):
        raise ValueError(f"Unknown signal event: {args.signal_event_id}")
    incoming = szse_a_share_list_evidence(
        payload,
        signal_event_id=args.signal_event_id,
        symbol=args.symbol,
        expected_name=args.expected_name,
        fetched_at=fetched_at,
        source_locator=str(relative_response).replace("\\", "/"),
    )
    evidence, events = merge_signal_evidence(store.evidence, incoming, store.events)
    validate_signal_events(events, store.signal_types)
    signal_dir = Path(args.signal_dir)
    evidence.to_csv(
        signal_dir / "signal_event_evidence.csv", index=False, encoding="utf-8-sig"
    )
    events.to_csv(signal_dir / "signal_events.csv", index=False, encoding="utf-8-sig")

    meta_path = signal_dir / "signal_store.meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "signal_event_rows": int(len(events)),
            "signal_evidence_rows": int(len(evidence)),
            "transmission_rule_rows": int(len(store.rules)),
            "last_verification": {
                "method": "official_szse_a_share_list_exact_match",
                "signal_event_id": args.signal_event_id,
                "source_record_id": incoming.iloc[0]["source_record_id"],
                "archive": str(relative_response).replace("\\", "/"),
            },
            "known_limits": [
                "official A-share list presence confirms listing presence, not continuous trading availability",
                "no signal propagates without both an explicit network edge and transmission rule",
                "display colours and normalized lifecycle strength are encodings, not measured value",
            ],
        }
    )
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    row = incoming.iloc[0]
    print(f"Official record: {args.symbol} {args.expected_name}")
    print(f"List date: {row['event_time']}")
    print(f"Signal evidence rows: {len(evidence)}")
    print("Propagation rules added: 0")
    print(f"Archived response: {relative_response}")


if __name__ == "__main__":
    main()
