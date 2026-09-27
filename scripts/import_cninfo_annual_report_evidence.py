from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from pypdf import PdfReader


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (
    ACTIVITY_PRODUCT_CANDIDATE_COLUMNS,
    COUNTERPARTY_CONCENTRATION_COLUMNS,
    PRODUCT_COLUMNS,
    counterparty_concentrations_from_annual_report,
    load_network_tables,
    product_mapping_candidates_from_activity,
    write_network_tables,
)


CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_ROOT = "http://static.cninfo.com.cn"
ANONYMOUS_ORDINALS = {"第一名", "第二名", "第三名", "第四名", "第五名"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive a CNINFO annual report and import reviewable product mappings "
            "plus anonymous customer/supplier concentration evidence."
        )
    )
    parser.add_argument("--symbol", default="002714")
    parser.add_argument("--org-id", default="9900022995")
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument(
        "--raw-root", default="data/external/a_share_industry_network/cninfo_reports"
    )
    parser.add_argument(
        "--archive-dir",
        default=None,
        help="Rebuild from an existing archive without network access.",
    )
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default=datetime.now().date().isoformat())
    parser.add_argument(
        "--announcement-id",
        default=None,
        help="Select one full annual report; otherwise use the latest full report.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_local_announcement(milliseconds: int) -> str:
    utc_time = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    return utc_time.astimezone(timezone(timedelta(hours=8))).isoformat(
        timespec="seconds"
    )


def fetch_announcement(
    *, symbol: str, org_id: str, start_date: str, end_date: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": f"{symbol},{org_id}",
        "searchkey": "",
        "secid": "",
        "category": "category_ndbg_szsh;",
        "trade": "",
        "seDate": f"{start_date}~{end_date}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = requests.post(CNINFO_QUERY_URL, data=payload, timeout=60)
    response.raise_for_status()
    query = response.json()
    return query, payload


def select_full_annual_report(
    query: dict[str, Any], announcement_id: str | None
) -> dict[str, Any]:
    candidates = []
    for item in query.get("announcements", []):
        title = re.sub(r"<[^>]+>", "", str(item.get("announcementTitle", "")))
        if re.fullmatch(r"\d{4}年年度报告", title):
            candidates.append(item)
    if announcement_id:
        candidates = [
            item
            for item in candidates
            if str(item.get("announcementId")) == announcement_id
        ]
    if not candidates:
        raise ValueError("No matching full annual report found")
    return max(candidates, key=lambda item: int(item["announcementTime"]))


def download_pdf(item: dict[str, Any], destination: Path) -> str:
    url = f"{CNINFO_STATIC_ROOT}/{str(item['adjunctUrl']).lstrip('/')}"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("CNINFO attachment did not contain a PDF")
    destination.write_bytes(response.content)
    return url


def _number(pattern: str, text: str, label: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Could not extract {label}")
    return float(match.group(1).replace(",", ""))


def _percent(pattern: str, text: str, label: str) -> float:
    return round(_number(pattern, text, label) / 100.0, 10)


def _ranked_rows(section: str, amount_word: str) -> list[tuple[str, float, float]]:
    pattern = rf"([第][一二三四五]名)\s+([\d,]+\.\d{{2}})\s+([\d.]+)%"
    rows = [
        (name, float(amount.replace(",", "")), round(float(share) / 100.0, 10))
        for name, amount, share in re.findall(pattern, section)
    ]
    if len(rows) != 5:
        raise ValueError(f"Expected five ranked {amount_word} rows, found {len(rows)}")
    if {row[0] for row in rows} != ANONYMOUS_ORDINALS:
        raise ValueError(
            "Named counterparties require human identity review before any company edge is created"
        )
    return rows


def extract_concentrations(
    pdf_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    page_texts = [(page.extract_text() or "") for page in reader.pages]
    customer_page = next(
        index for index, text in enumerate(page_texts) if "前五名客户合计销售金额" in text
    )
    supplier_page = next(
        index for index, text in enumerate(page_texts) if "前五名供应商合计采购金额" in text
    )
    relevant = "\n".join(page_texts[customer_page : supplier_page + 2])
    normalized = re.sub(r"\s+", " ", relevant)
    customer_section = normalized.split("公司主要销售客户情况", 1)[1].split(
        "公司主要供应商情况", 1
    )[0]
    supplier_section = normalized.split("公司主要供应商情况", 1)[1].split(
        "主要供应商其他情况说明", 1
    )[0]

    customer_amount = _number(
        r"前五名客户合计销售金额（元）\s*([\d,]+\.\d{2})",
        customer_section,
        "top-five customer amount",
    )
    customer_share = _percent(
        r"前五名客户合计销售金额占年度销售总额比例\s*([\d.]+)%",
        customer_section,
        "top-five customer share",
    )
    customer_related = _percent(
        r"前五名客户销售额中关联方销售额占年度销售总额比例\s*([\d.]+)%",
        customer_section,
        "related customer share",
    )
    supplier_amount = _number(
        r"前五名供应商合计采购金额（元）\s*([\d,]+\.\d{2})",
        supplier_section,
        "top-five supplier amount",
    )
    supplier_share = _percent(
        r"前五名供应商合计采购金额占年度采购总额比例\s*([\d.]+)%",
        supplier_section,
        "top-five supplier share",
    )
    supplier_related = _percent(
        r"前五名供应商采购额中关联方采购额占年度采购总额比例\s*([\d.]+)%",
        supplier_section,
        "related supplier share",
    )
    customer_rows = _ranked_rows(customer_section, "customer")
    supplier_rows = _ranked_rows(supplier_section, "supplier")
    if abs(sum(row[1] for row in customer_rows) - customer_amount) > 0.01:
        raise ValueError("Customer ranked amounts do not sum to the disclosed aggregate")
    if abs(sum(row[1] for row in supplier_rows) - supplier_amount) > 0.01:
        raise ValueError("Supplier ranked amounts do not sum to the disclosed aggregate")

    records = [
        {
            "counterparty_side": "customer",
            "aggregate_amount": customer_amount,
            "share_of_total": customer_share,
            "related_party_share_of_total": customer_related,
            "names_disclosed": False,
            "evidence_pages": str(customer_page + 1),
            "evidence_quote": (
                f"前五名客户合计销售金额（元）{customer_amount:,.2f}；"
                f"占年度销售总额比例 {customer_share:.2%}；"
                "客户名称仅披露为第一名至第五名。"
            ),
        },
        {
            "counterparty_side": "supplier",
            "aggregate_amount": supplier_amount,
            "share_of_total": supplier_share,
            "related_party_share_of_total": supplier_related,
            "names_disclosed": False,
            "evidence_pages": f"{supplier_page + 1}-{supplier_page + 2}",
            "evidence_quote": (
                f"前五名供应商合计采购金额（元）{supplier_amount:,.2f}；"
                f"占年度采购总额比例 {supplier_share:.2%}；"
                "供应商名称仅披露为第一名至第五名。"
            ),
        },
    ]
    audit = {
        "pdf_pages": len(reader.pages),
        "customer_evidence_page": customer_page + 1,
        "supplier_evidence_pages": [supplier_page + 1, supplier_page + 2],
        "customer_ranked_rows": customer_rows,
        "supplier_ranked_rows": supplier_rows,
        "counterparty_names_disclosed": False,
        "company_relation_edges_created": 0,
    }
    return records, audit


def _upsert(frame: pd.DataFrame, additions: pd.DataFrame, key: str, columns: list[str]) -> pd.DataFrame:
    return (
        pd.concat([frame, additions], ignore_index=True)
        .drop_duplicates(key, keep="last")
        .loc[:, columns]
        .reset_index(drop=True)
    )


def _upsert_reviewable_candidates(
    frame: pd.DataFrame, additions: pd.DataFrame
) -> pd.DataFrame:
    """Add new mappings without overwriting a prior human review decision."""
    return (
        pd.concat([additions, frame], ignore_index=True)
        .drop_duplicates("mapping_id", keep="last")
        .loc[:, ACTIVITY_PRODUCT_CANDIDATE_COLUMNS]
        .reset_index(drop=True)
    )


def main() -> None:
    args = parse_args()
    network_dir = Path(args.network_dir)
    if args.archive_dir:
        archive_dir = Path(args.archive_dir)
        query = json.loads((archive_dir / "query_response.json").read_text(encoding="utf-8"))
        query_meta = json.loads((archive_dir / "query.meta.json").read_text(encoding="utf-8"))
        item = select_full_annual_report(query, args.announcement_id)
        pdf_path = archive_dir / query_meta["pdf_filename"]
        first_available = query_meta["local_first_available_time_utc"]
        source_url = query_meta["pdf_url"]
    else:
        first_available = datetime.now(timezone.utc).isoformat(timespec="seconds")
        query, payload = fetch_announcement(
            symbol=args.symbol,
            org_id=args.org_id,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        item = select_full_annual_report(query, args.announcement_id)
        archive_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_dir = Path(args.raw_root) / archive_stamp
        archive_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"{args.symbol}_{item['announcementId']}_annual_report.pdf"
        pdf_path = archive_dir / pdf_filename
        source_url = download_pdf(item, pdf_path)
        (archive_dir / "query_response.json").write_text(
            json.dumps(query, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (archive_dir / "query_payload.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    records, extraction_audit = extract_concentrations(pdf_path)
    report_year_match = re.fullmatch(
        r"(\d{4})年年度报告",
        re.sub(r"<[^>]+>", "", str(item["announcementTitle"])),
    )
    if report_year_match is None:
        raise ValueError("Selected announcement title does not identify the report year")
    report_year = int(report_year_match.group(1))
    announcement_time = _iso_local_announcement(int(item["announcementTime"]))

    tables = load_network_tables(network_dir)
    listing = tables.listings[
        tables.listings["symbol"].astype(str).str.startswith(f"{args.symbol}.")
    ]
    if listing.empty:
        raise ValueError(f"Symbol not found in network: {args.symbol}")
    company_id = str(listing.iloc[0]["company_id"])
    main_activities = tables.business_activities[
        tables.business_activities["company_id"].astype(str).eq(company_id)
        & tables.business_activities["activity_type"].eq("main_business_description")
    ]
    exact = main_activities[
        main_activities["activity_text"].astype(str).str.contains("生猪的养殖与销售", regex=False)
    ]
    if len(exact) != 1:
        raise ValueError("Expected exactly one verbatim main-business activity for 生猪的养殖与销售")
    product, candidates = product_mapping_candidates_from_activity(
        exact.iloc[0],
        canonical_name="生猪",
        roles=["producer", "seller"],
        available_time=first_available,
        evidence_quote="生猪的养殖与销售",
        notes=(
            "Candidate only. Business-scope mentions of feed, slaughter and food are not "
            "promoted to current production facts."
        ),
    )
    concentration = counterparty_concentrations_from_annual_report(
        records,
        company_id=company_id,
        report_period_start=f"{report_year}-01-01",
        report_period_end=f"{report_year}-12-31",
        announcement_time=announcement_time,
        available_time=first_available,
        source="CNINFO official annual report PDF",
        source_record_id=str(item["announcementId"]),
    )
    tables.products = _upsert(tables.products, product, "product_id", PRODUCT_COLUMNS)
    tables.activity_product_candidates = _upsert_reviewable_candidates(
        tables.activity_product_candidates,
        candidates,
    )
    tables.counterparty_concentrations = _upsert(
        tables.counterparty_concentrations,
        concentration,
        "concentration_id",
        COUNTERPARTY_CONCENTRATION_COLUMNS,
    )
    manifest_path = write_network_tables(
        tables,
        network_dir,
        source_description=f"A-share network plus CNINFO annual-report archive {archive_dir}",
    )

    query_meta = {
        "local_first_available_time_utc": first_available,
        "announcement_time": announcement_time,
        "announcement_id": str(item["announcementId"]),
        "announcement_title": re.sub(r"<[^>]+>", "", str(item["announcementTitle"])),
        "report_period": f"{report_year}-01-01/{report_year}-12-31",
        "detail_url": (
            "http://www.cninfo.com.cn/new/disclosure/detail?"
            f"stockCode={args.symbol}&announcementId={item['announcementId']}"
            f"&orgId={args.org_id}&announcementTime={announcement_time[:10]}"
        ),
        "pdf_url": source_url,
        "pdf_filename": pdf_path.name,
        "pdf_sha256": sha256(pdf_path),
        "pdf_bytes": pdf_path.stat().st_size,
        "availability_policy": "available_at_local_first_fetch_time; official announcement time retained separately",
        "extraction_audit": extraction_audit,
    }
    (archive_dir / "query.meta.json").write_text(
        json.dumps(query_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    concentration.to_csv(
        archive_dir / "extracted_counterparty_concentrations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"Annual report: {pdf_path}")
    print(f"PDF SHA-256: {query_meta['pdf_sha256']}")
    status_counts = tables.activity_product_candidates["review_status"].value_counts().to_dict()
    print(
        "Product mappings in network: "
        f"{len(tables.activity_product_candidates)} "
        f"(review statuses: {status_counts})"
    )
    print(f"Concentration records: {len(concentration)}")
    print("Company relation edges created: 0 (counterparty names are anonymous)")
    print(f"Network manifest: {manifest_path}")


if __name__ == "__main__":
    main()
