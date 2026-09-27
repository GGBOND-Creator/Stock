from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (
    load_network_tables,
    review_activity_product_candidates,
    write_network_tables,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record an explicit human decision for product mapping candidates."
    )
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--mapping-id", action="append", required=True)
    parser.add_argument("--decision", choices=["approved", "rejected"], required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument(
        "--reviewed-at",
        default=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    parser.add_argument("--review-note", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tables = load_network_tables(args.network_dir)
    tables.activity_product_candidates = review_activity_product_candidates(
        tables.activity_product_candidates,
        tables.business_activities,
        mapping_ids=args.mapping_id,
        decision=args.decision,
        reviewer=args.reviewer,
        reviewed_at=args.reviewed_at,
        review_note=args.review_note,
    )
    manifest = write_network_tables(
        tables,
        args.network_dir,
        source_description="Prior A-share network plus explicit product mapping review",
    )
    reviewed = tables.activity_product_candidates[
        tables.activity_product_candidates["mapping_id"].isin(args.mapping_id)
    ]
    print(reviewed[["mapping_id", "role", "review_status", "reviewed_at"]].to_string(index=False))
    print(f"Network manifest: {manifest}")


if __name__ == "__main__":
    main()
