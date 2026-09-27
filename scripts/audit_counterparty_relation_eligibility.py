from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.industry_network import audit_counterparty_relation_eligibility


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether aggregate counterparty disclosures can create "
            "identified company relations."
        )
    )
    parser.add_argument("--as-of", required=True, help="Knowledge cutoff in ISO-8601.")
    parser.add_argument("--network-dir", default="data/industry_network/a_share")
    parser.add_argument(
        "--output", default="reports/counterparty_relation_eligibility.csv"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    network_dir = Path(args.network_dir)
    concentration_path = network_dir / "counterparty_concentrations.csv"
    relation_path = network_dir / "company_relations.csv"
    concentrations = pd.read_csv(concentration_path, dtype=str)
    relations = pd.read_csv(relation_path, dtype=str)
    audit = audit_counterparty_relation_eligibility(
        concentrations, as_of=args.as_of
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output, index=False, encoding="utf-8-sig")

    cutoff = pd.Timestamp(args.as_of)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    metadata = {
        "schema_version": "counterparty_relation_eligibility_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": cutoff.isoformat(),
        "input": {
            "path": concentration_path.as_posix(),
            "sha256": _sha256(concentration_path),
            "rows": len(concentrations),
        },
        "audited_rows_available_at_as_of": len(audit),
        "eligible_rows": int(
            audit["eligible_for_company_relation"].astype(bool).sum()
        ),
        "relation_rows_created": int(audit["relation_rows_created"].sum()),
        "existing_company_relation_rows": len(relations),
        "reason_counts": audit["reason_code"].value_counts().to_dict(),
        "writes_network_tables": False,
        "required_next_evidence": (
            "verbatim legal counterparty name, independent company identity, "
            "and reviewed available_time"
        ),
    }
    metadata_path = Path(f"{output}.meta.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary_path = output.with_suffix(".md")
    summary_path.write_text(
        _markdown_summary(metadata, audit), encoding="utf-8"
    )
    print(f"Audited disclosures: {len(audit)}")
    print(f"Eligible company relations: {metadata['eligible_rows']}")
    print(f"Company relations created: {metadata['relation_rows_created']}")
    print(f"Saved audit: {output}")
    print(f"Saved metadata: {metadata_path}")
    print(f"Saved summary: {summary_path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _markdown_summary(metadata: dict, audit: pd.DataFrame) -> str:
    rows = [
        "# 具名客户/供应商关系准入审计",
        "",
        f"知识时点：`{metadata['as_of']}`",
        "",
        "| 对手方方向 | 披露名称 | 准入决定 | 原因 | 创建关系 |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for _, item in audit.iterrows():
        disclosed = "是" if bool(item["names_disclosed"]) else "否"
        rows.append(
            f"| {item['counterparty_side']} | {disclosed} | {item['decision']} | "
            f"{item['reason_code']} | {int(item['relation_rows_created'])} |"
        )
    rows.extend(
        [
            "",
            f"结论：当前 {len(audit)} 条披露均不能生成具名公司关系；"
            f"`company_relations.csv` 仍为 {metadata['existing_company_relation_rows']} 行。",
            "",
            "任何新增关系至少需要：披露原文中的法定名称、独立公司身份依据，以及经过审核的可得时间。",
        ]
    )
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    main()
