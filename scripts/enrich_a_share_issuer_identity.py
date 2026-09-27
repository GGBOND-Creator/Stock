from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (
    BUSINESS_ACTIVITY_COLUMNS,
    NetworkTables,
    apply_cninfo_issuer_identity,
    business_activities_from_cninfo_profile,
    load_network_tables,
    write_network_tables,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map A-share symbols to CNINFO issuer orgIds and import pilot business evidence."
    )
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument(
        "--raw-root", default="data/external/a_share_industry_network/cninfo"
    )
    parser.add_argument(
        "--archive-dir",
        default=None,
        help="Rebuild from an existing CNINFO archive instead of downloading.",
    )
    parser.add_argument(
        "--profile-symbol",
        action="append",
        default=None,
        help="Six-digit symbol whose company profile should be imported; repeatable.",
    )
    return parser.parse_args()


def fetch_registry() -> tuple[pd.DataFrame, dict]:
    import requests

    url = "http://www.cninfo.com.cn/new/data/szse_stock.json"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    return pd.DataFrame(payload["stockList"]), payload


def fetch_profile(symbol: str) -> pd.DataFrame:
    import akshare as ak

    return ak.stock_profile_cninfo(symbol=symbol)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    profile_symbols = args.profile_symbol or ["002714"]

    if args.archive_dir:
        archive_dir = Path(args.archive_dir)
        query_meta = json.loads(
            (archive_dir / "query.meta.json").read_text(encoding="utf-8")
        )
        fetched_at = query_meta["fetched_at_utc"]
        registry = pd.read_csv(
            archive_dir / "stock_list.csv", dtype=str, keep_default_na=False
        )
    else:
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        registry, raw_payload = fetch_registry()
        archive_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = Path(args.raw_root) / archive_stamp
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "stock_list.json").write_text(
            json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8"
        )
        registry.to_csv(archive_dir / "stock_list.csv", index=False, encoding="utf-8-sig")

    profile_dir = archive_dir / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profiles: dict[str, pd.DataFrame] = {}
    for symbol in profile_symbols:
        profile_path = profile_dir / f"{symbol}.csv"
        if args.archive_dir:
            if not profile_path.exists():
                raise FileNotFoundError(f"Archived profile not found: {profile_path}")
            profile = pd.read_csv(profile_path, dtype=str, keep_default_na=False)
        else:
            profile = fetch_profile(symbol)
            profile.to_csv(profile_path, index=False, encoding="utf-8-sig")
        profiles[symbol] = profile

    if not args.archive_dir:
        (archive_dir / "query.meta.json").write_text(
            json.dumps(
                {
                    "fetched_at_utc": fetched_at,
                    "source": "CNINFO szse_stock.json and p_sysapi1133",
                    "registry_rows": int(len(registry)),
                    "profile_symbols": profile_symbols,
                    "availability_policy": "available_at_local_fetch_time",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    tables = load_network_tables(args.network_dir)
    mapped, identity_audit = apply_cninfo_issuer_identity(
        tables, registry, available_time=fetched_at
    )
    new_activities: list[pd.DataFrame] = []
    for symbol, profile in profiles.items():
        matched = identity_audit[
            identity_audit["symbol"].astype(str).str.split(".").str[0].eq(symbol)
        ]
        if matched.empty or pd.isna(matched.iloc[0]["cninfo_org_id"]):
            print(f"Skipped unmapped profile symbol: {symbol}")
            continue
        company_id = matched.iloc[0]["new_company_id"]
        issuer_id = matched.iloc[0]["cninfo_org_id"]
        activities = business_activities_from_cninfo_profile(
            profile,
            company_id=company_id,
            issuer_id=issuer_id,
            security_code=symbol,
            available_time=fetched_at,
        )
        new_activities.append(activities)
        if not profile.empty:
            company_mask = mapped.companies["company_id"].eq(company_id)
            full_name = profile.iloc[0].get("公司名称")
            registered_address = profile.iloc[0].get("注册地址")
            if pd.notna(full_name) and str(full_name).strip():
                mapped.companies.loc[company_mask, "company_name"] = str(full_name).strip()
            if pd.notna(registered_address) and str(registered_address).strip():
                mapped.companies.loc[company_mask, "registered_region"] = str(
                    registered_address
                ).strip()

    if new_activities:
        mapped.business_activities = (
            pd.concat(
                [mapped.business_activities, *new_activities], ignore_index=True
            )
            .drop_duplicates("activity_id", keep="first")
            [BUSINESS_ACTIVITY_COLUMNS]
        )

    manifest_path = write_network_tables(
        mapped,
        args.network_dir,
        source_description=(
            f"Prior A-share network enriched with CNINFO archive {archive_dir}"
        ),
    )
    audit_path = Path(args.network_dir) / "issuer_identity_map.csv"
    identity_audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    audit_meta_path = Path(f"{audit_path}.meta.json")
    audit_meta_path.write_text(
        json.dumps(
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_archive": str(archive_dir),
                "rows": int(len(identity_audit)),
                "mapped_rows": int(identity_audit["cninfo_org_id"].notna().sum()),
                "unmapped_rows": int(identity_audit["cninfo_org_id"].isna().sum()),
                "sha256": sha256(audit_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Issuer registry rows: {len(registry)}")
    print(f"Network listings mapped: {int(identity_audit['cninfo_org_id'].notna().sum())}")
    print(f"Network listings unmapped: {int(identity_audit['cninfo_org_id'].isna().sum())}")
    print(f"Durable company nodes after issuer merge: {len(mapped.companies)}")
    print(f"Business evidence rows: {len(mapped.business_activities)}")
    print(f"Raw archive: {archive_dir}")
    print(f"Identity audit: {audit_path}")
    print(f"Network manifest: {manifest_path}")


if __name__ == "__main__":
    main()
