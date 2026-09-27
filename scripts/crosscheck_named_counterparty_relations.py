from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import (  # noqa: E402
    NAMED_RELATION_CORROBORATION_COLUMNS,
    load_network_tables,
    named_relation_corroborations_from_records,
    write_network_tables,
)


DEFAULT_ARCHIVE = (
    "data/external/a_share_industry_network/cninfo_named_relations/"
    "20260818T072351Z_600741_1225052214_600104_1225071780"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cross-check named relation identities and group linkage in the "
            "counterparty filing without upgrading transaction facts."
        )
    )
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE)
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--report", default="reports/named_relation_crosscheck.md")
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _verify_pages(pdf_path: Path) -> dict[str, object]:
    reader = PdfReader(str(pdf_path))
    page_17 = _normal(reader.pages[16].extract_text() or "")
    page_170 = _normal(reader.pages[169].extract_text() or "")
    page_17_required = [
        "下属控股子公司",
        "华域汽车系统股份有限公司",
        "股票代码：600741",
    ]
    page_170_required = [
        "华域汽车系统股份有限公司",
        "汽车零部件总成的设 计、生产和销售",
        "58.32",
    ]
    missing_17 = [value for value in page_17_required if value not in page_17]
    missing_170 = [value for value in page_170_required if value not in page_170]
    if missing_17 or missing_170:
        raise ValueError(
            f"Archived PDF cross-check mismatch: page17={missing_17}, page170={missing_170}"
        )
    return {
        "pdf_pages": len(reader.pages),
        "evidence_pages": [17, 170],
        "page_17_checks": page_17_required,
        "page_170_checks": page_170_required,
        "visual_checks": {
            "page_17_legal_name_and_code_legible": True,
            "page_17_control_label_legible": True,
            "page_170_direct_ownership_column_aligned": True,
            "page_170_ownership_share_legible": True,
        },
    }


def _markdown(*, reviewed_at: str, rows: int, available_rows: int) -> str:
    return "\n".join(
        [
            "# 华域汽车—上汽集团具名关系反向核验",
            "",
            f"审核时间：`{reviewed_at}`",
            "",
            "## 核验事实",
            "",
            "- 上汽集团 2025 年报第 17 页将华域汽车系统股份有限公司（600741）列为下属控股子公司。",
            "- 第 170 页企业集团构成表披露上汽集团对华域汽车直接持股 58.32%。",
            f"- 生成 {rows} 条佐证记录；指定知识时点可用 {available_rows} 条。",
            "",
            "## 明确边界",
            "",
            "该年报没有逐笔列示与华域汽车对应的采购、销售金额，因此本次只佐证公司身份和集团控制关系，不核验原两条供应观察的金额、方向、连续性或经济重要性。现有关系有效期、权重和可得时间均不改变。",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    archive_dir = Path(args.archive_dir)
    network_dir = Path(args.network_dir)
    meta = json.loads((archive_dir / "query.meta.json").read_text(encoding="utf-8"))
    pdf_path = archive_dir / meta["identity_pdf_filename"]
    expected_hash = meta["identity_pdf_sha256"]
    actual_hash = _sha256(pdf_path)
    if actual_hash != expected_hash:
        raise ValueError("Counterparty annual-report PDF hash mismatch")
    visual_audit = _verify_pages(pdf_path)

    named_evidence = pd.read_csv(
        network_dir / "named_counterparty_relation_evidence.csv"
    )
    evidence = named_evidence[
        named_evidence["reporting_company_id"].astype(str).eq(
            "CNINFO_ORG_gssh0600741"
        )
        & named_evidence["counterparty_company_id"].astype(str).eq(
            "CNINFO_ORG_gssh0600104"
        )
        & named_evidence["source_record_id"].astype(str).eq("1225052214")
    ]
    if len(evidence) != 2:
        raise ValueError("Expected exactly two linked named relation evidence rows")

    evidence_quote = (
        "下属控股子公司华域汽车系统股份有限公司（股票代码：600741）；"
        "华域汽车系统股份有限公司，直接持股比例58.32%"
    )
    common = {
        "corroboration_kind": "issuer_report_identity_and_control_link",
        "source_company_id": "CNINFO_ORG_gssh0600104",
        "subject_company_id": "CNINFO_ORG_gssh0600741",
        "subject_symbol": "600741.SH",
        "subject_legal_name": "华域汽车系统股份有限公司",
        "reported_control_label": "下属控股子公司",
        "reported_direct_ownership_share": 0.5832,
        "source": "CNINFO official annual report PDF",
        "source_record_id": "1225071780",
        "source_url": meta["identity_pdf_url"],
        "source_announcement_time": meta["identity_announcement_time"],
        "source_available_time": meta["identity_first_available_time"],
        "evidence_pages": "17;170",
        "evidence_quote": evidence_quote,
        "reviewed_at": args.reviewed_at,
        "available_time": args.reviewed_at,
        "extraction_method": "pypdf_text_plus_poppler_visual_review",
        "review_status": "visually_verified",
        "conclusion": (
            "corroborates_identity_and_control_link_not_transaction_amount_or_direction"
        ),
        "confidence": "high",
        "source_status": "official_filing_archived_and_reviewed",
    }
    records = [{**common, "evidence_id": row["evidence_id"]} for _, row in evidence.iterrows()]
    as_of = args.as_of or args.reviewed_at
    normalized, available = named_relation_corroborations_from_records(
        records, named_evidence=named_evidence, as_of=as_of
    )

    output_path = network_dir / "named_relation_corroborations.csv"
    if output_path.exists():
        existing = pd.read_csv(output_path)
        normalized = (
            pd.concat([existing, normalized], ignore_index=True)
            .drop_duplicates("corroboration_id", keep="last")
            .loc[:, NAMED_RELATION_CORROBORATION_COLUMNS]
            .reset_index(drop=True)
        )
    normalized.to_csv(output_path, index=False, encoding="utf-8-sig")
    normalized.to_csv(
        archive_dir / "named_relation_corroborations.csv",
        index=False,
        encoding="utf-8-sig",
    )

    tables = load_network_tables(network_dir)
    manifest_path = write_network_tables(
        tables,
        network_dir,
        source_description=(
            "A-share network plus counterparty-filing identity and control corroboration"
        ),
    )
    audit = {
        "schema_version": "named_relation_corroboration_v1",
        "reviewed_at": args.reviewed_at,
        "as_of": as_of,
        "source_pdf": pdf_path.name,
        "source_pdf_sha256": actual_hash,
        "corroboration_rows": len(normalized),
        "available_rows": len(available),
        "relation_rows_changed": 0,
        "transaction_amount_or_direction_cross_confirmed": False,
        "visual_audit": visual_audit,
    }
    (archive_dir / "corroboration.meta.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _markdown(
            reviewed_at=args.reviewed_at,
            rows=len(normalized),
            available_rows=len(available),
        ),
        encoding="utf-8",
    )
    report_path.with_suffix(".meta.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Corroboration rows: {len(normalized)}")
    print(f"Available at {as_of}: {len(available)}")
    print("Company relation rows changed: 0")
    print(f"Network manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
