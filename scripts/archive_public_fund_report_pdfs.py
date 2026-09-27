from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


PDF_ROOT = "https://pdf.dfcfw.com/pdf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive and verify mirrored public-fund quarterly report PDFs."
    )
    parser.add_argument("--fund", action="append", required=True)
    parser.add_argument("--period-end", default="2026-06-30")
    parser.add_argument(
        "--reports-csv",
        default="data/external/public_fund/normalized/public_fund_reports.csv",
    )
    parser.add_argument(
        "--products-csv",
        default="data/external/public_fund/normalized/public_fund_products.csv",
    )
    parser.add_argument(
        "--holdings-csv",
        default="data/external/public_fund/normalized/public_fund_holdings.csv",
    )
    parser.add_argument(
        "--output-root", default="data/external/public_fund/report_pdfs"
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("（", "(").replace("）", ")")


def name_aliases(value: object) -> list[str]:
    compact = compact_text(str(value))
    aliases = {compact, compact.replace("(LOF)", "")}
    aliases.update({re.sub(r"[AC]$", "", item) for item in list(aliases)})
    return sorted(alias for alias in aliases if alias)


def quarterly_title_fragment(period_end: str) -> str:
    timestamp = pd.Timestamp(period_end)
    quarter = (timestamp.month - 1) // 3 + 1
    return f"{timestamp.year}年第{quarter}季度报告"


def choose_report(reports: pd.DataFrame, fund_code: str, period_end: str) -> pd.Series:
    candidates = reports[
        reports["fund_code"].astype(str).str.zfill(6).eq(fund_code)
        & reports["report_period_end"].astype(str).eq(period_end)
    ].copy()
    fragment = quarterly_title_fragment(period_end)
    quarterly = candidates[candidates["announcement_title"].str.contains(fragment, na=False)]
    if not quarterly.empty:
        candidates = quarterly
    if candidates.empty:
        raise ValueError(f"No report index entry for {fund_code} {period_end}")
    return candidates.sort_values("announcement_date").iloc[0]


def download_pdf(report_id: str, destination: Path) -> str:
    url = f"{PDF_ROOT}/H2_{report_id}_1.pdf"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"Report attachment is not a PDF: {url}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return url


def extract_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def verify_report(
    *,
    path: Path,
    product: pd.Series,
    report: pd.Series,
    expected_holdings: pd.DataFrame,
    downloaded_at: str,
    url: str,
) -> dict[str, object]:
    pages = extract_pages(path)
    full_text = "\n".join(pages)
    compact = compact_text(full_text)
    fund_code = str(product["fund_code"]).zfill(6)
    title_fragment = quarterly_title_fragment(str(report["report_period_end"]))
    name_candidates = name_aliases(product["full_name"]) + name_aliases(
        product["fund_name"]
    )
    identity_name_match = any(name and name in compact for name in name_candidates)
    code_match = fund_code in compact
    period_match = compact_text(title_fragment) in compact

    holding_checks = []
    evidence_pages = set()
    for holding in expected_holdings.itertuples(index=False):
        code = str(holding.instrument_id).split(".", 1)[0]
        raw_code = code.lstrip("0") or "0"
        name = str(holding.security_name)
        matching_pages = []
        for page_number, page_text in enumerate(pages, start=1):
            page_compact = compact_text(page_text)
            if compact_text(name) in page_compact or code in page_compact or raw_code in page_compact:
                matching_pages.append(page_number)
        if matching_pages:
            evidence_pages.update(matching_pages)
        holding_checks.append(
            {
                "instrument_id": holding.instrument_id,
                "security_name": name,
                "matched_pages": matching_pages,
            }
        )
    matched_holdings = sum(bool(item["matched_pages"]) for item in holding_checks)
    share_class_table_detected = any(
        marker in compact
        for marker in ["下属分级基金", "下属基金份额类别", "各类别基金份额"]
    )
    fund_codes_in_document = sorted(
        set(re.findall(r"(?<!\d)\d{6}(?!\d)", full_text))
    )
    quality_status = (
        "pdf_content_verified_against_index_and_disclosed_holdings"
        if identity_name_match and code_match and period_match and matched_holdings >= min(8, len(expected_holdings))
        else "pdf_downloaded_verification_incomplete"
    )
    return {
        "fund_code": fund_code,
        "fund_name": product["fund_name"],
        "full_name": product["full_name"],
        "report_period_end": report["report_period_end"],
        "report_id": report["source_record_id"],
        "index_title": report["announcement_title"],
        "index_announcement_date": report["announcement_date"],
        "index_available_time": report["available_time"],
        "downloaded_at": downloaded_at,
        "mirror_url": url,
        "pdf_file": str(path),
        "pdf_sha256": sha256(path),
        "page_count": len(pages),
        "text_character_count": len(full_text),
        "identity_name_match": identity_name_match,
        "fund_code_match": code_match,
        "report_period_match": period_match,
        "expected_holding_rows": len(expected_holdings),
        "matched_holding_rows": matched_holdings,
        "holding_evidence_pages": sorted(evidence_pages),
        "holding_checks": holding_checks,
        "share_class_table_detected": share_class_table_detected,
        "six_digit_codes_in_document": fund_codes_in_document,
        "quality_status": quality_status,
        "known_limits": [
            "PDF is archived from an Eastmoney mirror, not yet from the fund manager's official host",
            "announcement date is supplied by the report index and may not appear inside the PDF",
            "text matching verifies document identity and holdings presence, not every numeric table cell",
        ],
    }


def main() -> None:
    args = parse_args()
    reports = pd.read_csv(args.reports_csv, dtype={"fund_code": str})
    products = pd.read_csv(args.products_csv, dtype={"fund_code": str})
    holdings = pd.read_csv(args.holdings_csv, dtype={"fund_code": str})
    for frame in [reports, products, holdings]:
        frame["fund_code"] = frame["fund_code"].astype(str).str.zfill(6)

    downloaded_at = datetime.now().astimezone().isoformat(timespec="seconds")
    output_root = Path(args.output_root)
    audit_records = []
    for raw_code in args.fund:
        fund_code = str(raw_code).zfill(6)
        product_rows = products[products["fund_code"].eq(fund_code)]
        if len(product_rows) != 1:
            raise ValueError(f"Expected one product row for {fund_code}")
        product = product_rows.iloc[0]
        report = choose_report(reports, fund_code, args.period_end)
        expected = holdings[
            holdings["fund_code"].eq(fund_code)
            & holdings["report_period_end"].astype(str).eq(args.period_end)
        ]
        if expected.empty:
            raise ValueError(f"No normalized holdings for {fund_code} {args.period_end}")
        report_id = str(report["source_record_id"])
        destination = (
            output_root
            / fund_code
            / args.period_end
            / f"{fund_code}_{args.period_end}_{report_id}.pdf"
        )
        url = download_pdf(report_id, destination)
        audit = verify_report(
            path=destination,
            product=product,
            report=report,
            expected_holdings=expected,
            downloaded_at=downloaded_at,
            url=url,
        )
        audit_path = destination.with_suffix(".audit.json")
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        audit_records.append(audit)
        print(
            f"{fund_code}: {audit['quality_status']}; pages={audit['page_count']}; "
            f"holdings={audit['matched_holding_rows']}/{audit['expected_holding_rows']}"
        )

    summary_path = output_root / f"report_pdf_verification_{args.period_end}.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": "public_fund_report_pdf_audit_v1",
                "created_at": downloaded_at,
                "report_period_end": args.period_end,
                "records": audit_records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    incomplete = [
        row for row in audit_records if not str(row["quality_status"]).startswith("pdf_content_verified")
    ]
    if incomplete:
        raise SystemExit(f"PDF verification incomplete for {len(incomplete)} fund(s)")
    print(f"Saved verification summary: {summary_path}")


if __name__ == "__main__":
    main()
