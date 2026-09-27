from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.capital_control import (
    CAPITAL_POOL_COLUMNS,
    CONTROLLER_COLUMNS,
    CONTROL_RELATION_COLUMNS,
)
from stock_model.public_fund import (
    CAPITAL_POSITION_COLUMNS,
    PUBLIC_FUND_HOLDING_CHANGE_COLUMNS,
    PUBLIC_FUND_HOLDING_COLUMNS,
    PUBLIC_FUND_PRODUCT_COLUMNS,
    PUBLIC_FUND_REPORT_COLUMNS,
    capital_control_tables_from_fund,
    build_reported_holding_changes,
    normalize_fund_announcement_reports,
    normalize_fund_holdings,
    normalize_fund_overview,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch public-fund product, manager, custodian, and disclosed quarterly "
            "holding evidence without inferring transaction identities."
        )
    )
    parser.add_argument(
        "--fund",
        action="append",
        required=True,
        help="Fund code; repeat for a small reproducible sample.",
    )
    parser.add_argument(
        "--year",
        default=str(datetime.now().year),
        help="Holding report year requested from Eastmoney.",
    )
    parser.add_argument("--raw-root", default="data/external/public_fund")
    parser.add_argument("--capital-root", default="data/capital_control/a_share")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_observation_time(raw_root: Path, fund_code: str, fallback: str) -> str:
    """Recover the earliest local observation time from immutable raw archives."""

    fund_root = raw_root / fund_code
    candidates = [path for path in fund_root.iterdir() if path.is_dir()] if fund_root.exists() else []
    if not candidates:
        return fallback
    try:
        first = min(candidates, key=lambda path: path.name)
        parsed = datetime.strptime(first.name.replace("_", "+"), "%Y-%m-%dT%H%M%S%z")
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        return fallback


def upsert_csv(path: Path, frame: pd.DataFrame, key: str, columns: list[str]) -> None:
    if path.exists() and path.stat().st_size:
        previous = pd.read_csv(path, dtype=str)
        combined = pd.concat([previous, frame], ignore_index=True)
    else:
        combined = frame.copy()
    for column in columns:
        if column not in combined.columns:
            combined[column] = pd.NA
    combined = combined[columns].drop_duplicates(key, keep="last")
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False, encoding="utf-8-sig")


def replace_partitions_csv(
    path: Path,
    frame: pd.DataFrame,
    *,
    partition_column: str,
    columns: list[str],
) -> None:
    """Replace complete fund partitions so corrected identifiers cannot linger."""

    if path.exists() and path.stat().st_size:
        previous = pd.read_csv(path, dtype=str)
        replacing = set(frame[partition_column].astype(str))
        previous = previous[~previous[partition_column].astype(str).isin(replacing)]
        combined = pd.concat([previous, frame], ignore_index=True)
    else:
        combined = frame.copy()
    for column in columns:
        if column not in combined.columns:
            combined[column] = pd.NA
    path.parent.mkdir(parents=True, exist_ok=True)
    combined[columns].to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    try:
        import akshare as ak
    except ImportError as exc:
        raise SystemExit("Install akshare first: pip install akshare") from exc

    available_time = datetime.now().astimezone().isoformat(timespec="seconds")
    raw_root = Path(args.raw_root)
    capital_root = Path(args.capital_root)
    normalized_root = raw_root / "normalized"
    product_rows = []
    holding_frames = []
    report_frames = []
    controller_frames = []
    pool_frames = []
    relation_frames = []
    position_frames = []
    archive_records = []

    for raw_code in args.fund:
        fund_code = str(raw_code).strip().zfill(6)
        product_available_time = first_observation_time(
            raw_root, fund_code, available_time
        )
        overview = ak.fund_overview_em(fund_code)
        report_index = ak.fund_announcement_report_em(fund_code)
        holdings = ak.fund_portfolio_hold_em(fund_code, args.year)
        normalized_reports = normalize_fund_announcement_reports(
            report_index, fund_code=fund_code, fetched_at=available_time
        )
        report_availability = (
            normalized_reports.dropna(subset=["report_period_end"])
            .groupby("report_period_end")["available_time"]
            .min()
            .to_dict()
        )
        product = normalize_fund_overview(
            overview, fund_code=fund_code, available_time=product_available_time
        )
        normalized_holdings = normalize_fund_holdings(
            holdings,
            fund_code=fund_code,
            available_time=available_time,
            report_available_times=report_availability,
        )
        product_rows.append(product)
        holding_frames.append(normalized_holdings)
        report_frames.append(normalized_reports)
        controllers, pools, relations, positions = capital_control_tables_from_fund(
            product.iloc[0], normalized_holdings
        )
        controller_frames.append(controllers)
        pool_frames.append(pools)
        relation_frames.append(relations)
        position_frames.append(positions)

        archive_dir = raw_root / fund_code / available_time.replace(":", "").replace("+", "_")
        archive_dir.mkdir(parents=True, exist_ok=True)
        overview_path = archive_dir / "fund_overview_raw.csv"
        report_index_path = archive_dir / "fund_report_index_raw.csv"
        holdings_path = archive_dir / f"fund_holdings_{args.year}_raw.csv"
        overview.to_csv(overview_path, index=False, encoding="utf-8-sig")
        report_index.to_csv(report_index_path, index=False, encoding="utf-8-sig")
        holdings.to_csv(holdings_path, index=False, encoding="utf-8-sig")
        archive_records.append(
            {
                "fund_code": fund_code,
                "requested_year": args.year,
                "available_time": available_time,
                "source": "AkShare via Eastmoney fundf10",
                "overview_url": f"https://fundf10.eastmoney.com/jbgk_{fund_code}.html",
                "holdings_url": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html",
                "overview_file": str(overview_path),
                "overview_sha256": sha256(overview_path),
                "report_index_file": str(report_index_path),
                "report_index_sha256": sha256(report_index_path),
                "holdings_file": str(holdings_path),
                "holdings_sha256": sha256(holdings_path),
                "overview_rows": len(overview),
                "report_index_rows": len(report_index),
                "holding_rows": len(holdings),
                "limitations": [
                    "manager relationship available_time is local first observation",
                    "holding available_time uses the indexed report announcement date at day end",
                    "the announcement index date was not yet verified against the original PDF",
                    "quarter-end holdings do not identify the exact transaction path",
                    "manager names establish a reported relationship, not personal ownership of fund assets",
                ],
            }
        )

    products = pd.concat(product_rows, ignore_index=True)
    holdings = pd.concat(holding_frames, ignore_index=True)
    reports = pd.concat(report_frames, ignore_index=True)
    scope_warnings = []
    for product in products.itertuples(index=False):
        product_holdings = holdings[holdings["fund_id"].eq(product.fund_id)]
        if product_holdings.empty or pd.isna(product.net_assets):
            continue
        latest_period = product_holdings["report_period_end"].max()
        latest_value = product_holdings.loc[
            product_holdings["report_period_end"].eq(latest_period), "market_value"
        ].sum()
        if latest_value > float(product.net_assets) * 1.05:
            scope_warnings.append(
                {
                    "fund_code": product.fund_code,
                    "report_period_end": latest_period,
                    "disclosed_holdings_value_cny": float(latest_value),
                    "overview_net_assets_cny": float(product.net_assets),
                    "warning": "holding portfolio scope may differ from overview share-class net-assets scope",
                }
            )
    replace_partitions_csv(
        normalized_root / "public_fund_products.csv",
        products,
        partition_column="fund_id",
        columns=PUBLIC_FUND_PRODUCT_COLUMNS,
    )
    holdings_master_path = normalized_root / "public_fund_holdings.csv"
    replace_partitions_csv(
        holdings_master_path,
        holdings,
        partition_column="fund_id",
        columns=PUBLIC_FUND_HOLDING_COLUMNS,
    )
    replace_partitions_csv(
        normalized_root / "public_fund_reports.csv",
        reports,
        partition_column="fund_id",
        columns=PUBLIC_FUND_REPORT_COLUMNS,
    )
    master_holdings = pd.read_csv(holdings_master_path, dtype={"fund_code": str})
    master_holdings["fund_code"] = master_holdings["fund_code"].str.zfill(6)
    holding_changes = build_reported_holding_changes(master_holdings)
    replace_partitions_csv(
        normalized_root / "public_fund_holding_changes.csv",
        holding_changes,
        partition_column="fund_id",
        columns=PUBLIC_FUND_HOLDING_CHANGE_COLUMNS,
    )
    upsert_csv(capital_root / "controllers.csv", pd.concat(controller_frames, ignore_index=True), "controller_id", CONTROLLER_COLUMNS)
    replace_partitions_csv(
        capital_root / "capital_pools.csv",
        pd.concat(pool_frames, ignore_index=True),
        partition_column="capital_pool_id",
        columns=CAPITAL_POOL_COLUMNS,
    )
    replace_partitions_csv(
        capital_root / "control_relations.csv",
        pd.concat(relation_frames, ignore_index=True),
        partition_column="capital_pool_id",
        columns=CONTROL_RELATION_COLUMNS,
    )
    replace_partitions_csv(
        capital_root / "capital_positions.csv",
        pd.concat(position_frames, ignore_index=True),
        partition_column="capital_pool_id",
        columns=CAPITAL_POSITION_COLUMNS,
    )
    meta_path = normalized_root / "public_fund_fetch.meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    run_record = {
        "created_at": available_time,
        "requested_funds": [str(code).zfill(6) for code in args.fund],
        "requested_year": args.year,
        "archive_records": archive_records,
        "scope_warnings": scope_warnings,
    }
    previous_runs = []
    if meta_path.exists():
        previous = json.loads(meta_path.read_text(encoding="utf-8"))
        if "runs" in previous:
            previous_runs = list(previous["runs"])
        elif "archive_records" in previous:
            previous_runs = [
                {
                    "created_at": previous.get("created_at"),
                    "requested_funds": previous.get("requested_funds", []),
                    "requested_year": previous.get("requested_year"),
                    "archive_records": previous.get("archive_records", []),
                }
            ]
    meta_path.write_text(
        json.dumps(
            {
                "schema_version": "public_fund_evidence_v1",
                "updated_at": available_time,
                "runs": previous_runs + [run_record],
                "known_limits": [
                    "Eastmoney/AkShare is a third-party aggregation source",
                    "report publication time was not independently verified",
                    "holdings are snapshots and are not capital-flow events",
                    "no probability distribution is generated from holdings alone",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Funds fetched: {len(products)}")
    print(f"Products: {normalized_root / 'public_fund_products.csv'}")
    print(f"Reports: {normalized_root / 'public_fund_reports.csv'} ({len(reports)} rows)")
    print(f"Holdings: {normalized_root / 'public_fund_holdings.csv'} ({len(holdings)} rows)")
    print(
        f"Holding changes: {normalized_root / 'public_fund_holding_changes.csv'} "
        f"({len(holding_changes)} rows)"
    )
    print(f"Capital-control positions: {capital_root / 'capital_positions.csv'}")
    print("No transaction-controller probability was inferred from quarterly holdings.")


if __name__ == "__main__":
    main()
