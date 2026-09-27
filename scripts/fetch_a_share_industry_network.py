from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (
    add_missing_snapshot_candidates,
    apply_cninfo_issuer_identity,
    load_network_tables,
    merge_incremental_network_refresh,
    seed_from_spot_snapshot,
    tables_from_baostock,
    write_network_tables,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch free BaoStock company/listing/industry data and build the A-share network."
    )
    parser.add_argument(
        "--output-dir", default="data/industry_network/a_share", help="Internal network directory."
    )
    parser.add_argument(
        "--raw-root",
        default="data/external/a_share_industry_network/baostock",
        help="Root used to archive untouched source extracts.",
    )
    parser.add_argument(
        "--archive-dir",
        default=None,
        help="Rebuild from a prior raw archive instead of querying BaoStock.",
    )
    parser.add_argument(
        "--spot-candidate-snapshot",
        default="data/realtime/a_share_spot.csv",
        help="Optional dated AkShare snapshot used only for symbols missing from BaoStock.",
    )
    return parser.parse_args()


def query_result_to_frame(result: object) -> pd.DataFrame:
    rows: list[list[str]] = []
    while result.error_code == "0" and result.next():
        rows.append(result.get_row_data())
    if result.error_code != "0":
        raise RuntimeError(f"BaoStock query failed: {result.error_code} {result.error_msg}")
    return pd.DataFrame(rows, columns=result.fields)


def fetch_baostock() -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import baostock as bs
    except ImportError as exc:
        raise RuntimeError("BaoStock is not installed in the current environment.") from exc

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")
    try:
        basic = query_result_to_frame(bs.query_stock_basic())
        industry = query_result_to_frame(bs.query_stock_industry())
    finally:
        bs.logout()
    return basic, industry


def main() -> None:
    args = parse_args()
    prior_tables = None
    prior_refresh_time = None
    prior_manifest_path = Path(args.output_dir) / "network.meta.json"
    if prior_manifest_path.exists():
        prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
        prior_refresh_time = prior_manifest["created_at_utc"]
        prior_tables = load_network_tables(args.output_dir)
    if args.archive_dir:
        archive_dir = Path(args.archive_dir)
        query_meta = json.loads(
            (archive_dir / "query.meta.json").read_text(encoding="utf-8")
        )
        fetched_at = query_meta["fetched_at_utc"]
        basic = pd.read_csv(archive_dir / "stock_basic.csv", dtype=str, keep_default_na=False)
        industry = pd.read_csv(
            archive_dir / "stock_industry.csv", dtype=str, keep_default_na=False
        )
    else:
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        basic, industry = fetch_baostock()

        archive_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = Path(args.raw_root) / archive_stamp
        archive_dir.mkdir(parents=True, exist_ok=True)
        basic_path = archive_dir / "stock_basic.csv"
        industry_path = archive_dir / "stock_industry.csv"
        basic.to_csv(basic_path, index=False, encoding="utf-8-sig")
        industry.to_csv(industry_path, index=False, encoding="utf-8-sig")
        (archive_dir / "query.meta.json").write_text(
            json.dumps(
                {
                    "fetched_at_utc": fetched_at,
                    "source": "BaoStock query_stock_basic/query_stock_industry",
                    "basic_rows": int(len(basic)),
                    "industry_rows": int(len(industry)),
                    "availability_policy": "available_at_local_fetch_time",
                    "warning": "Historical dates are facts learned at fetched_at_utc unless a separate archival availability source is added.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    tables = tables_from_baostock(basic, industry, fetched_at=fetched_at)
    added_candidates = 0
    candidate_path = Path(args.spot_candidate_snapshot) if args.spot_candidate_snapshot else None
    if candidate_path and candidate_path.exists():
        candidate_spot = pd.read_csv(candidate_path)
        candidate_tables = seed_from_spot_snapshot(candidate_spot)
        tables, added_candidates = add_missing_snapshot_candidates(
            tables, candidate_tables
        )
    identity_map_path = Path(args.output_dir) / "issuer_identity_map.csv"
    identity_source_description = ""
    if identity_map_path.exists():
        identity_map = pd.read_csv(identity_map_path, dtype=str)
        known_identity = identity_map[identity_map["cninfo_org_id"].notna()].copy()
        registry = pd.DataFrame(
            {
                "code": known_identity["symbol"].str.split(".").str[0],
                "orgId": known_identity["cninfo_org_id"],
                "zwjc": known_identity["cninfo_name"].fillna("unknown"),
                "category": "A股",
            }
        )
        identity_available_time = (
            known_identity["available_time"].dropna().min()
            if known_identity["available_time"].notna().any()
            else fetched_at
        )
        tables, _ = apply_cninfo_issuer_identity(
            tables,
            registry,
            available_time=identity_available_time,
        )
        identity_source_description = f"; reused {identity_map_path}"
    if prior_tables is not None and prior_refresh_time is not None:
        tables = merge_incremental_network_refresh(
            prior_tables,
            tables,
            previous_refresh_time=prior_refresh_time,
            current_refresh_time=fetched_at,
        )
    manifest_path = write_network_tables(
        tables,
        args.output_dir,
        source_description=(
            f"BaoStock archive {archive_dir}; "
            f"missing-symbol candidates from {candidate_path if candidate_path else 'none'}"
            f"{identity_source_description}"
        ),
    )
    print(f"Companies: {len(tables.companies)}")
    print(f"Listings: {len(tables.listings)}")
    print(f"Industries: {len(tables.industries)}")
    print(f"Industry memberships: {len(tables.memberships)}")
    print(f"Lifecycle events: {len(tables.lifecycle_events)}")
    print(f"Company-to-company relations: {len(tables.relations)}")
    print(f"Stale/unverified missing-symbol candidates added: {added_candidates}")
    print(f"Raw archive: {archive_dir}")
    print(f"Network manifest: {manifest_path}")


if __name__ == "__main__":
    main()
