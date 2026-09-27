from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (  # noqa: E402
    NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS,
    RELATION_COLUMNS,
    company_relations_from_named_counterparty_evidence,
    load_network_tables,
    write_network_tables,
)


CNINFO_QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_ROOT = "http://static.cninfo.com.cn"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import visually reviewed, named annual-report counterparty relations."
    )
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument(
        "--raw-root",
        default="data/external/a_share_industry_network/cninfo_named_relations",
    )
    parser.add_argument("--archive-dir", default=None)
    parser.add_argument("--reporting-pdf", default=None)
    parser.add_argument("--identity-pdf", default=None)
    parser.add_argument("--reporting-first-available-time", default=None)
    parser.add_argument("--identity-first-available-time", default=None)
    parser.add_argument("--reviewed-at", default=None)
    parser.add_argument("--archive-name", default=None)
    parser.add_argument("--as-of", default=None)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _query(symbol: str, org_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
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
        "seDate": "2025-01-01~2026-08-18",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = requests.post(CNINFO_QUERY_URL, data=payload, timeout=60)
    response.raise_for_status()
    return response.json(), payload


def _select(query: dict[str, Any], announcement_id: str) -> dict[str, Any]:
    for item in query.get("announcements", []):
        if str(item.get("announcementId")) == announcement_id:
            title = re.sub(r"<[^>]+>", "", str(item.get("announcementTitle", "")))
            if "年度报告" not in title or "摘要" in title:
                raise ValueError(f"Announcement is not a full annual report: {title}")
            return item
    raise ValueError(f"Announcement not found: {announcement_id}")


def _download(item: dict[str, Any], destination: Path) -> str:
    url = f"{CNINFO_STATIC_ROOT}/{str(item['adjunctUrl']).lstrip('/')}"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("CNINFO attachment did not contain a PDF")
    destination.write_bytes(response.content)
    return url


def _copy_or_download(
    *,
    local_path: str | None,
    item: dict[str, Any],
    destination: Path,
) -> tuple[str, str]:
    if local_path:
        source_path = Path(local_path)
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        shutil.copy2(source_path, destination)
        return f"{CNINFO_STATIC_ROOT}/{str(item['adjunctUrl']).lstrip('/')}", "provided_local_archive"
    return _download(item, destination), "downloaded_during_import"


def _announcement_time(item: dict[str, Any]) -> str:
    value = datetime.fromtimestamp(
        int(item["announcementTime"]) / 1000, tz=timezone.utc
    )
    return value.isoformat(timespec="seconds")


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_texts(path: Path) -> list[str]:
    return [_normal(page.extract_text() or "") for page in PdfReader(str(path)).pages]


def _must_contain(text: str, quote: str, label: str) -> None:
    if quote not in text:
        raise ValueError(f"{label} quote not found in the archived PDF")


def extract_and_verify_evidence(
    *,
    reporting_pdf: Path,
    identity_pdf: Path,
    reporting_source_url: str,
    identity_source_url: str,
    reporting_source_record_id: str,
    identity_source_record_id: str,
    reporting_announcement_time: str,
    identity_announcement_time: str,
    source_available_time: str,
    identity_available_time: str,
    reviewed_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reporting_pages = _page_texts(reporting_pdf)
    identity_pages = _page_texts(identity_pdf)
    reporting_identity_page = 4
    purchase_page = 178
    sale_page = 179
    identity_page = 1
    reporting_identity_quote = (
        "公司、本公司、华域汽车 指 华域汽车系统股份有限公司"
    )
    purchase_quote = (
        "上汽集团 商品及材料采购 协商确定 153,169,367.40"
    )
    sale_quote = "上汽集团 销售商品 协商确定 5,438,818,642.01"
    identity_quote = (
        "公司代码：600104 公司简称：上汽集团 上海汽车集团股份有限公司 2025 年年度报告"
    )
    _must_contain(reporting_pages[reporting_identity_page - 1], reporting_identity_quote, "reporting identity")
    _must_contain(reporting_pages[purchase_page - 1], purchase_quote, "purchase")
    _must_contain(reporting_pages[sale_page - 1], sale_quote, "sale")
    _must_contain(identity_pages[identity_page - 1], "公司代码：600104", "counterparty code")
    _must_contain(identity_pages[identity_page - 1], "公司简称：上汽集团", "counterparty short name")
    _must_contain(identity_pages[identity_page - 1], "上海汽车集团股份有限公司", "counterparty legal name")

    common = {
        "reporting_company_id": "CNINFO_ORG_gssh0600741",
        "reporting_symbol": "600741.SH",
        "reporting_legal_name": "华域汽车系统股份有限公司",
        "counterparty_company_id": "CNINFO_ORG_gssh0600104",
        "counterparty_symbol": "600104.SH",
        "counterparty_legal_name": "上海汽车集团股份有限公司",
        "counterparty_name_in_filing": "上汽集团",
        "report_period_start": "2025-01-01",
        "report_period_end": "2025-12-31",
        "relation_type": "supplies",
        "currency": "CNY",
        "announcement_time": reporting_announcement_time,
        "source_available_time": source_available_time,
        "identity_announcement_time": identity_announcement_time,
        "identity_available_time": identity_available_time,
        "relation_available_time": reviewed_at,
        "source": "CNINFO official annual report PDF",
        "source_record_id": reporting_source_record_id,
        "source_url": reporting_source_url,
        "reporting_identity_evidence_page": "4",
        "reporting_identity_evidence_quote": reporting_identity_quote,
        "identity_source": "CNINFO official annual report PDF",
        "identity_source_record_id": identity_source_record_id,
        "identity_source_url": identity_source_url,
        "identity_evidence_page": "1",
        "identity_evidence_quote": identity_quote,
        "extraction_method": "pypdf_text_plus_visual_page_review",
        "review_status": "visually_verified_and_identity_confirmed",
        "reviewed_at": reviewed_at,
        "confidence": "high",
        "source_status": "official_filing_archived_and_reviewed",
    }
    records = [
        {
            **common,
            "transaction_direction": "purchase_from",
            "product_or_service": "商品及材料",
            "transaction_amount": 153169367.40,
            "evidence_page": "178",
            "evidence_quote": purchase_quote,
        },
        {
            **common,
            "transaction_direction": "sale_to",
            "product_or_service": "商品",
            "transaction_amount": 5438818642.01,
            "evidence_page": "179",
            "evidence_quote": sale_quote,
        },
    ]
    visual_audit = {
        "method": "rendered_pages_reviewed_with_poppler_and_image_inspection",
        "reporting_pages": [4, 178, 179],
        "identity_pages": [1],
        "checks": {
            "table_headers_and_units_clear": True,
            "purchase_counterparty_and_amount_column_aligned": True,
            "sale_counterparty_and_amount_column_aligned": True,
            "identity_cover_code_short_name_legal_name_aligned": True,
        },
        "reviewed_at": reviewed_at,
    }
    return records, visual_audit


def _load_or_fetch(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.archive_dir:
        archive = Path(args.archive_dir)
        meta = json.loads((archive / "query.meta.json").read_text(encoding="utf-8"))
        return meta, {"archive": archive}
    if not all(
        [
            args.reporting_pdf,
            args.identity_pdf,
            args.reporting_first_available_time,
            args.identity_first_available_time,
            args.reviewed_at,
        ]
    ):
        raise ValueError(
            "Fresh import requires both PDFs, both first-available times, and --reviewed-at"
        )
    return {}, {"archive": None}


def main() -> None:
    args = parse_args()
    network_dir = Path(args.network_dir)
    if args.archive_dir:
        meta, context = _load_or_fetch(args)
        archive_dir = context["archive"]
        reporting_item = meta["reporting_item"]
        identity_item = meta["identity_item"]
        reporting_pdf = archive_dir / meta["reporting_pdf_filename"]
        identity_pdf = archive_dir / meta["identity_pdf_filename"]
        reporting_source_url = meta["reporting_pdf_url"]
        identity_source_url = meta["identity_pdf_url"]
        reporting_source_record_id = str(reporting_item["announcementId"])
        identity_source_record_id = str(identity_item["announcementId"])
        reporting_announcement_time = meta["reporting_announcement_time"]
        identity_announcement_time = meta["identity_announcement_time"]
        source_available_time = meta["reporting_first_available_time"]
        identity_available_time = meta["identity_first_available_time"]
        reviewed_at = meta["reviewed_at"]
    else:
        reporting_query, reporting_payload = _query("600741", "gssh0600741")
        identity_query, identity_payload = _query("600104", "gssh0600104")
        reporting_item = _select(reporting_query, "1225052214")
        identity_item = _select(identity_query, "1225071780")
        archive_name = args.archive_name or "20260818T072351Z_600741_1225052214_600104_1225071780"
        archive_dir = Path(args.raw_root) / archive_name
        archive_dir.mkdir(parents=True, exist_ok=True)
        reporting_pdf = archive_dir / "600741_1225052214_annual_report.pdf"
        identity_pdf = archive_dir / "600104_1225071780_annual_report.pdf"
        reporting_source_url, _ = _copy_or_download(
            local_path=args.reporting_pdf,
            item=reporting_item,
            destination=reporting_pdf,
        )
        identity_source_url, _ = _copy_or_download(
            local_path=args.identity_pdf,
            item=identity_item,
            destination=identity_pdf,
        )
        (archive_dir / "reporting_query_response.json").write_text(
            json.dumps(reporting_query, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (archive_dir / "reporting_query_payload.json").write_text(
            json.dumps(reporting_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (archive_dir / "identity_query_response.json").write_text(
            json.dumps(identity_query, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (archive_dir / "identity_query_payload.json").write_text(
            json.dumps(identity_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reporting_announcement_time = _announcement_time(reporting_item)
        identity_announcement_time = _announcement_time(identity_item)
        source_available_time = args.reporting_first_available_time
        identity_available_time = args.identity_first_available_time
        reviewed_at = args.reviewed_at

    records, visual_audit = extract_and_verify_evidence(
        reporting_pdf=reporting_pdf,
        identity_pdf=identity_pdf,
        reporting_source_url=reporting_source_url,
        identity_source_url=identity_source_url,
        reporting_source_record_id=str(reporting_item["announcementId"]),
        identity_source_record_id=str(identity_item["announcementId"]),
        reporting_announcement_time=reporting_announcement_time,
        identity_announcement_time=identity_announcement_time,
        source_available_time=source_available_time,
        identity_available_time=identity_available_time,
        reviewed_at=reviewed_at,
    )
    as_of = args.as_of or reviewed_at
    tables = load_network_tables(network_dir)
    evidence, relations = company_relations_from_named_counterparty_evidence(
        records, companies=tables.companies, as_of=as_of
    )

    evidence_path = network_dir / "named_counterparty_relation_evidence.csv"
    if evidence_path.exists():
        existing_evidence = pd.read_csv(evidence_path)
        evidence = (
            pd.concat([existing_evidence, evidence], ignore_index=True)
            .drop_duplicates("evidence_id", keep="last")
            .loc[:, NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS]
            .reset_index(drop=True)
        )
    evidence.to_csv(evidence_path, index=False, encoding="utf-8-sig")

    tables.relations = (
        pd.concat([tables.relations, relations], ignore_index=True)
        .drop_duplicates("relation_id", keep="last")
        .loc[:, RELATION_COLUMNS]
        .reset_index(drop=True)
    )
    manifest_path = write_network_tables(
        tables,
        network_dir,
        source_description=(
            "A-share network plus independently identified CNINFO annual-report "
            "counterparty relation evidence"
        ),
    )
    meta = {
        "schema_version": "named_counterparty_relation_evidence_v1",
        "reporting_item": reporting_item,
        "identity_item": identity_item,
        "reporting_pdf_filename": reporting_pdf.name,
        "identity_pdf_filename": identity_pdf.name,
        "reporting_pdf_url": reporting_source_url,
        "identity_pdf_url": identity_source_url,
        "reporting_pdf_sha256": sha256(reporting_pdf),
        "identity_pdf_sha256": sha256(identity_pdf),
        "reporting_first_available_time": source_available_time,
        "identity_first_available_time": identity_available_time,
        "reporting_announcement_time": reporting_announcement_time,
        "identity_announcement_time": identity_announcement_time,
        "reviewed_at": reviewed_at,
        "relation_as_of": as_of,
        "visual_audit": visual_audit,
        "relation_rows_created_or_retained": len(tables.relations),
        "availability_policy": (
            "relation_available_time is the earliest time after source, independent identity, "
            "and review evidence are all available"
        ),
    }
    (archive_dir / "query.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    evidence.to_csv(
        archive_dir / "named_counterparty_relation_evidence.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (archive_dir / "visual_verification.json").write_text(
        json.dumps(visual_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Archived evidence: {archive_dir}")
    print(f"Named evidence rows: {len(evidence)}")
    print(f"Company relation rows: {len(tables.relations)}")
    print(f"Relation rows visible at {as_of}: {len(relations)}")
    print(f"Network manifest: {manifest_path}")


if __name__ == "__main__":
    main()
