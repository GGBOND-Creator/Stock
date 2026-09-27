"""Build a read-only, evidence-aware view of a network-signal snapshot."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


REPORT_SCHEMA_VERSION = "network_signal_report_v1"


def build_signal_report_model(
    *,
    symbol: str,
    snapshot: pd.DataFrame,
    signal_types: pd.DataFrame,
    events: pd.DataFrame,
    evidence: pd.DataFrame,
    rules: pd.DataFrame,
    companies: pd.DataFrame,
    listings: pd.DataFrame,
    products: pd.DataFrame,
    mappings: pd.DataFrame,
) -> dict[str, Any]:
    """Join one listing's snapshot state to events and temporally labelled evidence."""
    _require_columns(snapshot, [
        "as_of", "object_type", "object_id", "signal_type", "concentration",
        "direct_contribution", "propagated_contribution", "source_event_count",
        "quality_status",
    ], "snapshot")
    _require_columns(signal_types, [
        "signal_type", "display_name", "display_color", "display_channel"
    ], "signal_types")
    _require_columns(events, [
        "signal_event_id", "emitter_object_type", "emitter_object_id",
        "signal_type", "initial_strength", "unit", "available_time",
        "effective_time", "expires_time", "source", "source_record_id",
        "evidence_kind", "quality_status",
    ], "events")
    _require_columns(evidence, [
        "evidence_id", "signal_event_id", "source", "source_record_id",
        "raw_numeric_value", "raw_unit", "raw_text", "available_time",
        "source_locator", "evidence_kind", "verification_method", "quality_status",
        "dimension_type", "dimension_id",
    ], "evidence")
    _require_columns(companies, ["company_id", "company_name"], "companies")
    _require_columns(listings, [
        "listing_id", "company_id", "symbol", "exchange", "listing_date"
    ], "listings")
    _require_columns(products, ["product_id", "canonical_name"], "products")
    _require_columns(mappings, [
        "company_id", "product_id", "role", "review_status", "reviewed_at"
    ], "mappings")

    listing_rows = listings[listings["symbol"].astype(str) == symbol]
    if len(listing_rows) != 1:
        raise ValueError(f"Expected one listing for {symbol}, found {len(listing_rows)}")
    listing = listing_rows.iloc[0]
    company_rows = companies[
        companies["company_id"].astype(str) == str(listing["company_id"])
    ]
    if len(company_rows) != 1:
        raise ValueError(
            f"Expected one company for {listing['company_id']}, found {len(company_rows)}"
        )
    company = company_rows.iloc[0]

    as_of_values = pd.to_datetime(
        snapshot["as_of"], errors="raise", utc=True, format="mixed"
    ).drop_duplicates()
    if len(as_of_values) != 1:
        raise ValueError("Signal report requires exactly one snapshot as_of value")
    as_of = pd.Timestamp(as_of_values.iloc[0])

    object_keys = {
        ("listing", str(listing["listing_id"])),
        ("company", str(company["company_id"])),
    }
    relevant = snapshot[
        snapshot.apply(
            lambda row: (str(row["object_type"]), str(row["object_id"])) in object_keys,
            axis=1,
        )
    ].copy()
    numeric_columns = [
        "concentration", "direct_contribution", "propagated_contribution"
    ]
    for column in numeric_columns:
        relevant[column] = pd.to_numeric(relevant[column], errors="raise")
    nonzero = relevant[
        relevant[numeric_columns].abs().max(axis=1) > 0
    ].copy()
    if nonzero.empty:
        raise ValueError(f"No non-zero network signals found for {symbol}")

    type_lookup = signal_types.set_index("signal_type", drop=False)
    normalized_events = events.copy()
    for column in ["available_time", "effective_time", "expires_time"]:
        normalized_events[column] = pd.to_datetime(
            normalized_events[column], errors="coerce", utc=True, format="mixed"
        )
    normalized_evidence = evidence.copy()
    normalized_evidence["available_time"] = pd.to_datetime(
        normalized_evidence["available_time"],
        errors="coerce",
        utc=True,
        format="mixed",
    )

    signals: list[dict[str, Any]] = []
    object_order = {"listing": 0, "company": 1}
    nonzero["_order"] = nonzero["object_type"].map(object_order).fillna(9)
    nonzero = nonzero.sort_values(["_order", "signal_type"], kind="stable")
    for _, state in nonzero.iterrows():
        signal_type = str(state["signal_type"])
        if signal_type not in type_lookup.index:
            raise ValueError(f"Unknown signal type in snapshot: {signal_type}")
        type_row = type_lookup.loc[signal_type]
        matching_events = normalized_events[
            (normalized_events["emitter_object_type"].astype(str) == str(state["object_type"]))
            & (normalized_events["emitter_object_id"].astype(str) == str(state["object_id"]))
            & (normalized_events["signal_type"].astype(str) == signal_type)
            & (normalized_events["available_time"] <= as_of)
            & (normalized_events["effective_time"] <= as_of)
            & (
                normalized_events["expires_time"].isna()
                | (normalized_events["expires_time"] > as_of)
            )
        ].sort_values(["available_time", "signal_event_id"], kind="stable")
        if matching_events.empty:
            raise ValueError(
                f"Snapshot signal has no event available at as_of: {state['object_id']} {signal_type}"
            )

        evidence_rows = normalized_evidence[
            normalized_evidence["signal_event_id"].astype(str).isin(
                matching_events["signal_event_id"].astype(str)
            )
        ].sort_values(["available_time", "evidence_id"], kind="stable")
        evidence_items = [
            _evidence_item(row, as_of=as_of) for _, row in evidence_rows.iterrows()
        ]
        source_event = matching_events.iloc[-1]
        signals.append(
            {
                "key": f"{state['object_type']}:{state['object_id']}:{signal_type}",
                "object_type": str(state["object_type"]),
                "object_id": str(state["object_id"]),
                "object_label": _object_label(str(state["object_type"])),
                "object_name": _object_name(
                    str(state["object_type"]), listing=listing, company=company
                ),
                "signal_type": signal_type,
                "signal_name": str(type_row["display_name"]),
                "display_color": str(type_row["display_color"]),
                "display_channel": str(type_row["display_channel"]),
                "concentration": float(state["concentration"]),
                "direct_contribution": float(state["direct_contribution"]),
                "propagated_contribution": float(state["propagated_contribution"]),
                "source_event_count": int(float(state["source_event_count"])),
                "snapshot_quality": str(state["quality_status"]),
                "event": {
                    "source": _text(source_event["source"]),
                    "source_record_id": _text(source_event["source_record_id"]),
                    "available_time": _iso(source_event["available_time"]),
                    "evidence_kind": _text(source_event["evidence_kind"]),
                    "initial_strength": float(source_event["initial_strength"]),
                    "unit": _text(source_event["unit"]),
                },
                "evidence": evidence_items,
                "known_evidence_count": sum(
                    item["available_at_snapshot"] for item in evidence_items
                ),
                "later_evidence_count": sum(
                    not item["available_at_snapshot"] for item in evidence_items
                ),
            }
        )

    active_rules = _active_rule_count(rules, as_of=as_of)
    product_nodes = _product_nodes(
        snapshot=snapshot,
        products=products,
        mappings=mappings,
        company_id=str(company["company_id"]),
        as_of=as_of,
    )
    later_evidence_count = sum(item["later_evidence_count"] for item in signals)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "title": f"{company['company_name']}网络信号",
        "symbol": symbol,
        "as_of": as_of.isoformat(),
        "company": {
            "company_id": str(company["company_id"]),
            "company_name": str(company["company_name"]),
        },
        "listing": {
            "listing_id": str(listing["listing_id"]),
            "symbol": str(listing["symbol"]),
            "exchange": str(listing["exchange"]),
            "listing_date": _text(listing["listing_date"]),
        },
        "signals": signals,
        "products": product_nodes,
        "nonzero_signal_count": len(signals),
        "transmission_rule_count": active_rules,
        "later_evidence_count": later_evidence_count,
        "all_propagated_zero": all(
            item["propagated_contribution"] == 0.0 for item in signals
        ),
    }


def render_signal_report(model: dict[str, Any]) -> str:
    """Render a standalone report with an inline, escaped data model."""
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    title = html.escape(str(model["title"]))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #f5f7f8;
  --surface: #ffffff;
  --surface-2: #eef1f2;
  --text: #172126;
  --muted: #607078;
  --border: #cbd3d7;
  --accent: #146c94;
  --accent-soft: #dceff7;
  --warning: #8a5a00;
  --warning-soft: #fff1c7;
  --production: #2e7d32;
  --lifecycle: #455a64;
  --neutral: #9aa6ac;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #15191b;
    --surface: #202629;
    --surface-2: #2a3235;
    --text: #eef3f5;
    --muted: #aab7bd;
    --border: #465257;
    --accent: #69b9dc;
    --accent-soft: #173b4c;
    --warning: #ffd479;
    --warning-soft: #493814;
    --production: #52bd67;
    --lifecycle: #a7b4ba;
    --neutral: #69767c;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }}
main {{ width: min(100%, 1000px); margin: 0 auto; padding: 24px; }}
header {{ display: flex; align-items: end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }}
h1, h2, p, dl, dd {{ margin: 0; }}
h1 {{ font-size: 24px; font-weight: 500; letter-spacing: 0; }}
h2 {{ font-size: 18px; font-weight: 500; letter-spacing: 0; }}
.meta, .small {{ color: var(--muted); font-size: 13px; }}
.flow {{ display: grid; grid-template-columns: minmax(0,1fr) 110px minmax(0,1fr) 110px minmax(0,1fr); gap: 10px; align-items: stretch; }}
.node {{ min-width: 0; min-height: 154px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); padding: 16px; text-align: left; display: flex; flex-direction: column; justify-content: space-between; gap: 14px; }}
button.node {{ cursor: pointer; font: inherit; }}
button.node:hover {{ border-color: var(--accent); }}
button.node[aria-pressed="true"] {{ border-color: var(--accent); outline: 2px solid var(--accent); outline-offset: 1px; }}
button.node:focus-visible {{ outline: 3px solid var(--accent); outline-offset: 2px; }}
.node-head {{ display: flex; align-items: center; gap: 9px; font-weight: 500; }}
.mark {{ width: 17px; height: 17px; flex: 0 0 17px; display: inline-block; }}
.mark.lifecycle {{ border: 2px solid var(--lifecycle); }}
.mark.production {{ border-radius: 50%; background: var(--production); box-shadow: 0 0 0 5px color-mix(in srgb, var(--production) 18%, transparent); }}
.mark.neutral {{ border-radius: 50%; background: var(--neutral); }}
.node-body {{ display: grid; gap: 5px; min-width: 0; }}
.node-body span {{ overflow-wrap: anywhere; }}
.edge {{ min-width: 0; display: grid; place-content: center; text-align: center; gap: 7px; }}
.edge-line {{ width: 100%; height: 1px; background: var(--border); position: relative; }}
.edge-line::after {{ content: ""; position: absolute; right: 1px; top: -3px; width: 7px; height: 7px; border-top: 1px solid var(--border); border-right: 1px solid var(--border); transform: rotate(45deg); }}
.temporal-note {{ margin-top: 18px; padding: 12px 14px; background: var(--warning-soft); color: var(--warning); border-left: 3px solid var(--warning); }}
.detail {{ margin-top: 22px; padding-top: 20px; border-top: 1px solid var(--border); }}
.detail-head {{ display: flex; align-items: start; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }}
.badge {{ display: inline-flex; align-items: center; min-height: 26px; padding: 3px 9px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 13px; }}
.badge.later {{ background: var(--warning-soft); color: var(--warning); }}
.detail-grid {{ display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px 28px; }}
dt {{ color: var(--muted); font-size: 13px; margin-bottom: 4px; }}
dd {{ overflow-wrap: anywhere; }}
.evidence-switch {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0 0; }}
.evidence-switch button {{ border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--text); padding: 7px 10px; font: inherit; cursor: pointer; }}
.evidence-switch button[aria-pressed="true"] {{ background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }}
.legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 20px; color: var(--muted); font-size: 13px; }}
.legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
footer {{ margin-top: 20px; color: var(--muted); font-size: 13px; }}
@media (max-width: 660px) {{
  main {{ padding: 16px; }}
  .flow {{ grid-template-columns: minmax(0,1fr); }}
  .node {{ min-height: 120px; }}
  .edge {{ grid-template-columns: 1fr auto; place-content: initial; align-items: center; text-align: left; padding: 0 12px; }}
  .edge-line {{ width: 1px; height: 34px; grid-column: 2; grid-row: 1 / span 2; }}
  .edge-line::after {{ right: -3px; top: auto; bottom: 1px; transform: rotate(135deg); }}
  .detail-grid {{ grid-template-columns: minmax(0,1fr); }}
}}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1 id="report-title"></h1>
      <p class="meta" id="report-symbol"></p>
    </div>
    <p class="meta" id="report-status"></p>
  </header>

  <section class="flow" id="network-flow" aria-label="上市阶段、企业和产品的网络信号"></section>
  <p class="temporal-note" id="temporal-note" hidden></p>

  <section class="detail" aria-labelledby="detail-title">
    <div class="detail-head">
      <div>
        <h2 id="detail-title"></h2>
        <p class="small" id="detail-subtitle"></p>
      </div>
      <span class="badge" id="detail-badge"></span>
    </div>
    <dl class="detail-grid">
      <div><dt>快照时信号来源</dt><dd id="event-source"></dd></div>
      <div><dt>独立证据来源</dt><dd id="evidence-source"></dd></div>
      <div><dt>原始事实文本</dt><dd id="raw-text"></dd></div>
      <div><dt>原始数值</dt><dd id="raw-number"></dd></div>
      <div><dt>显示编码</dt><dd id="display-value"></dd></div>
      <div><dt>证据质量</dt><dd id="evidence-quality"></dd></div>
      <div><dt>证据可得时间</dt><dd id="evidence-time"></dd></div>
      <div><dt>核验方法</dt><dd id="verification-method"></dd></div>
    </dl>
    <div class="evidence-switch" id="evidence-switch" aria-label="选择证据记录"></div>
  </section>

  <div class="legend">
    <span><i class="mark lifecycle" aria-hidden="true"></i>生命周期直接信号</span>
    <span><i class="mark production" aria-hidden="true"></i>生产活动直接信号</span>
    <span><i class="mark neutral" aria-hidden="true"></i>无信号或未获传播</span>
  </div>
  <footer id="report-footer"></footer>
</main>
<script id="report-data" type="application/json">{payload}</script>
<script>
(() => {{
  const model = JSON.parse(document.getElementById("report-data").textContent);
  const flow = document.getElementById("network-flow");
  const fields = {{
    title: document.getElementById("detail-title"),
    subtitle: document.getElementById("detail-subtitle"),
    badge: document.getElementById("detail-badge"),
    eventSource: document.getElementById("event-source"),
    evidenceSource: document.getElementById("evidence-source"),
    rawText: document.getElementById("raw-text"),
    rawNumber: document.getElementById("raw-number"),
    displayValue: document.getElementById("display-value"),
    quality: document.getElementById("evidence-quality"),
    evidenceTime: document.getElementById("evidence-time"),
    verification: document.getElementById("verification-method"),
    switcher: document.getElementById("evidence-switch")
  }};
  let selectedSignal = model.signals.find(item => item.signal_type === "production.activity") || model.signals[0];
  let selectedEvidenceIndex = 0;

  const formatNumber = value => Number(value).toFixed(1);
  const text = value => value === null || value === undefined || value === "" ? "未记录" : String(value);
  const evidenceStatus = item => item.available_at_snapshot ? "快照时已可得" : "快照后取得，仅作后续核验";
  const nodeMark = signal => signal.display_channel === "glow" ? "production" : "lifecycle";

  const appendNodeContent = (node, markClass, label, name, value, context) => {{
    const head = document.createElement("span");
    head.className = "node-head";
    const mark = document.createElement("i");
    mark.className = `mark ${{markClass}}`;
    mark.setAttribute("aria-hidden", "true");
    head.append(mark, document.createTextNode(text(label)));
    const body = document.createElement("span");
    body.className = "node-body";
    const nameLine = document.createElement("span");
    nameLine.className = "small";
    nameLine.textContent = text(name);
    const valueLine = document.createElement("span");
    valueLine.textContent = text(value);
    const contextLine = document.createElement("span");
    contextLine.className = "small";
    contextLine.textContent = text(context);
    body.append(nameLine, valueLine, contextLine);
    node.append(head, body);
  }};

  const makeSignalNode = signal => {{
    const button = document.createElement("button");
    button.type = "button";
    button.className = "node";
    button.dataset.signalKey = signal.key;
    button.setAttribute("aria-pressed", String(signal.key === selectedSignal.key));
    appendNodeContent(
      button,
      nodeMark(signal),
      signal.object_label,
      signal.object_name,
      `${{signal.signal_name}} ${{formatNumber(signal.concentration)}}`,
      `直接 ${{formatNumber(signal.direct_contribution)}} · 传播 ${{formatNumber(signal.propagated_contribution)}}`
    );
    button.addEventListener("click", () => {{ selectedSignal = signal; selectedEvidenceIndex = 0; renderSelection(); }});
    return button;
  }};

  const makeEdge = label => {{
    const edge = document.createElement("div");
    edge.className = "edge";
    edge.setAttribute("aria-label", `${{label}}，传播贡献为零`);
    const line = document.createElement("div");
    line.className = "edge-line";
    line.setAttribute("aria-hidden", "true");
    const labelText = document.createElement("span");
    labelText.className = "small";
    labelText.textContent = label;
    const valueText = document.createElement("span");
    valueText.className = "small";
    valueText.textContent = "传播 0.0";
    edge.append(line, labelText, valueText);
    return edge;
  }};

  model.signals.forEach((signal, index) => {{
    flow.appendChild(makeSignalNode(signal));
    if (index === 0) flow.appendChild(makeEdge("上市 → 企业"));
  }});
  if (model.products.length) {{
    flow.appendChild(makeEdge("企业 → 产品"));
    const product = model.products[0];
    const node = document.createElement("div");
    node.className = "node";
    appendNodeContent(
      node,
      "neutral",
      "产品",
      product.product_name,
      `当前信号 ${{formatNumber(product.concentration)}}`,
      `传播 ${{formatNumber(product.propagated_contribution)}} · ${{model.transmission_rule_count === 0 ? "未获传播规则授权" : "按规则计算"}}`
    );
    flow.appendChild(node);
  }}

  const renderEvidence = () => {{
    const items = selectedSignal.evidence;
    const item = items[selectedEvidenceIndex] || null;
    fields.switcher.replaceChildren();
    items.forEach((entry, index) => {{
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-pressed", String(index === selectedEvidenceIndex));
      button.textContent = `${{index + 1}} · ${{evidenceStatus(entry)}}`;
      button.addEventListener("click", () => {{ selectedEvidenceIndex = index; renderEvidence(); }});
      fields.switcher.appendChild(button);
    }});
    if (!item) {{
      fields.badge.textContent = "无独立证据记录";
      fields.badge.className = "badge later";
      fields.evidenceSource.textContent = "未记录";
      fields.rawText.textContent = "未记录";
      fields.rawNumber.textContent = "未记录";
      fields.quality.textContent = "未记录";
      fields.evidenceTime.textContent = "未记录";
      fields.verification.textContent = "未记录";
      return;
    }}
    fields.badge.textContent = evidenceStatus(item);
    fields.badge.className = item.available_at_snapshot ? "badge" : "badge later";
    fields.evidenceSource.textContent = text(item.source);
    fields.rawText.textContent = text(item.raw_text);
    fields.rawNumber.textContent = text(item.raw_numeric_display);
    fields.quality.textContent = text(item.quality_status);
    fields.evidenceTime.textContent = text(item.available_time);
    fields.verification.textContent = text(item.verification_method);
  }};

  const renderSelection = () => {{
    document.querySelectorAll("button[data-signal-key]").forEach(button => {{
      button.setAttribute("aria-pressed", String(button.dataset.signalKey === selectedSignal.key));
    }});
    fields.title.textContent = `${{selectedSignal.signal_name}}证据`;
    fields.subtitle.textContent = `${{selectedSignal.object_label}} · ${{selectedSignal.signal_type}}`;
    fields.eventSource.textContent = `${{text(selectedSignal.event.source)}} · ${{text(selectedSignal.event.source_record_id)}}`;
    fields.displayValue.textContent = `直接 ${{formatNumber(selectedSignal.direct_contribution)}} · 传播 ${{formatNumber(selectedSignal.propagated_contribution)}}`;
    renderEvidence();
  }};

  document.getElementById("report-title").textContent = model.title;
  document.getElementById("report-symbol").textContent = `${{model.symbol}} · 时点 ${{model.as_of}}`;
  document.getElementById("report-status").textContent = `${{model.nonzero_signal_count}} 条非零信号 · ${{model.transmission_rule_count}} 条传播规则`;
  document.getElementById("report-footer").textContent = `只读报告 · 快照传播贡献${{model.all_propagated_zero ? "全部为零" : "含非零值"}} · 不构成投资建议`;
  const temporalNote = document.getElementById("temporal-note");
  if (model.later_evidence_count > 0) {{
    temporalNote.hidden = false;
    temporalNote.textContent = `${{model.later_evidence_count}} 条证据取得于快照时点之后，已保留为后续核验，不回填到快照状态。`;
  }}
  renderSelection();
}})();
</script>
</body>
</html>
"""


def write_signal_report(
    output_path: str | Path,
    model: dict[str, Any],
    *,
    input_paths: Iterable[str | Path],
) -> tuple[Path, Path]:
    """Write the report and a sidecar containing exact input hashes."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_signal_report(model), encoding="utf-8")
    inputs = []
    for input_path in input_paths:
        path = Path(input_path)
        inputs.append(
            {
                "path": path.as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    metadata = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": model["symbol"],
        "as_of": model["as_of"],
        "nonzero_signal_count": model["nonzero_signal_count"],
        "transmission_rule_count": model["transmission_rule_count"],
        "later_evidence_count": model["later_evidence_count"],
        "all_propagated_zero": model["all_propagated_zero"],
        "output": output.as_posix(),
        "inputs": inputs,
        "warnings": [
            "Display strengths are encodings, not production quantity, valuation, return, or probability.",
            "Evidence obtained after the snapshot is labelled as later verification and does not alter the earlier state.",
        ],
    }
    metadata_path = Path(f"{output}.meta.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output, metadata_path


def _evidence_item(row: pd.Series, *, as_of: pd.Timestamp) -> dict[str, Any]:
    available_time = row["available_time"]
    available_at_snapshot = bool(
        pd.notna(available_time) and pd.Timestamp(available_time) <= as_of
    )
    raw_unit = _text(row["raw_unit"])
    raw_value = row["raw_numeric_value"]
    if raw_unit == "not_reported" and _missing(raw_value):
        numeric_display = "未披露"
    elif raw_unit == "not_applicable" and _missing(raw_value):
        numeric_display = "不适用"
    elif _missing(raw_value):
        numeric_display = "未记录"
    else:
        numeric_display = f"{raw_value} {raw_unit}".strip()
    return {
        "evidence_id": _text(row["evidence_id"]),
        "source": _text(row["source"]),
        "source_record_id": _text(row["source_record_id"]),
        "raw_numeric_display": numeric_display,
        "raw_unit": raw_unit,
        "raw_text": _text(row["raw_text"]),
        "available_time": _iso(available_time),
        "available_at_snapshot": available_at_snapshot,
        "availability_label": (
            "available_at_snapshot" if available_at_snapshot else "available_after_snapshot"
        ),
        "source_locator": _text(row["source_locator"]),
        "evidence_kind": _text(row["evidence_kind"]),
        "verification_method": _text(row["verification_method"]),
        "quality_status": _text(row["quality_status"]),
        "dimension_type": _text(row["dimension_type"]),
        "dimension_id": _text(row["dimension_id"]),
    }


def _product_nodes(
    *,
    snapshot: pd.DataFrame,
    products: pd.DataFrame,
    mappings: pd.DataFrame,
    company_id: str,
    as_of: pd.Timestamp,
) -> list[dict[str, Any]]:
    frame = mappings[
        (mappings["company_id"].astype(str) == company_id)
        & (mappings["role"].astype(str) == "producer")
        & (mappings["review_status"].astype(str) == "approved")
    ].copy()
    frame["reviewed_at"] = pd.to_datetime(
        frame["reviewed_at"], errors="coerce", utc=True, format="mixed"
    )
    frame = frame[frame["reviewed_at"] <= as_of]
    product_lookup = products.set_index("product_id", drop=False)
    nodes = []
    for product_id in frame["product_id"].astype(str).drop_duplicates():
        if product_id not in product_lookup.index:
            raise ValueError(f"Approved mapping references unknown product: {product_id}")
        state = snapshot[
            (snapshot["object_type"].astype(str) == "product")
            & (snapshot["object_id"].astype(str) == product_id)
        ]
        concentration = pd.to_numeric(state["concentration"], errors="raise").abs().max()
        propagated = pd.to_numeric(
            state["propagated_contribution"], errors="raise"
        ).abs().max()
        nodes.append(
            {
                "product_id": product_id,
                "product_name": str(product_lookup.loc[product_id, "canonical_name"]),
                "concentration": 0.0 if pd.isna(concentration) else float(concentration),
                "propagated_contribution": 0.0 if pd.isna(propagated) else float(propagated),
            }
        )
    return nodes


def _active_rule_count(rules: pd.DataFrame, *, as_of: pd.Timestamp) -> int:
    if rules.empty:
        return 0
    _require_columns(rules, ["available_time", "valid_from", "valid_to"], "rules")
    frame = rules.copy()
    for column in ["available_time", "valid_from", "valid_to"]:
        frame[column] = pd.to_datetime(
            frame[column], errors="coerce", utc=True, format="mixed"
        )
    active = frame[
        (frame["available_time"] <= as_of)
        & (frame["valid_from"] <= as_of)
        & (frame["valid_to"].isna() | (frame["valid_to"] > as_of))
    ]
    return len(active)


def _object_label(object_type: str) -> str:
    return {"listing": "上市阶段", "company": "企业", "product": "产品"}.get(
        object_type, object_type
    )


def _object_name(object_type: str, *, listing: pd.Series, company: pd.Series) -> str:
    if object_type == "listing":
        return str(listing["symbol"])
    if object_type == "company":
        return str(company["company_name"])
    return object_type


def _require_columns(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")


def _missing(value: Any) -> bool:
    return value is None or (not isinstance(value, (list, dict)) and pd.isna(value))


def _text(value: Any) -> str:
    return "" if _missing(value) else str(value)


def _iso(value: Any) -> str:
    return "" if _missing(value) else pd.Timestamp(value).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
