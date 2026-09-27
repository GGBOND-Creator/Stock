"""A temporal, evidence-gated signal field for network objects.

The signal field is deliberately separate from the A-share industry-network
contract.  A signal is an observation or an explicitly declared modelling
event; it is not a claim that a colour or a glow is a measured fact.  Rules
and relation edges must both exist before a signal can propagate.
"""

from __future__ import annotations

import json
import hashlib
import re
import math
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

import pandas as pd


SIGNAL_SCHEMA_VERSION = "network_signal_field_v1"

OBJECT_TYPES = {
    "company",
    "listing",
    "industry",
    "product",
    "natural_unit",
    "capital_pool",
}

SIGNAL_TYPE_COLUMNS = [
    "signal_type",
    "display_name",
    "description",
    "default_unit",
    "polarity",
    "display_color",
    "display_channel",
    "default_half_life_days",
    "evidence_status",
    "quality_status",
]

EVENT_COLUMNS = [
    "signal_event_id",
    "emitter_object_type",
    "emitter_object_id",
    "signal_type",
    "initial_strength",
    "unit",
    "event_time",
    "available_time",
    "effective_time",
    "expires_time",
    "half_life_days",
    "decay_method",
    "source",
    "source_record_id",
    "evidence_kind",
    "confidence",
    "quality_status",
]

EVIDENCE_COLUMNS = [
    "evidence_id",
    "signal_event_id",
    "source",
    "source_record_id",
    "claim_type",
    "claim_value",
    "dimension_type",
    "dimension_id",
    "raw_numeric_value",
    "raw_unit",
    "raw_text",
    "event_time",
    "available_time",
    "source_locator",
    "evidence_kind",
    "verification_method",
    "quality_status",
]

RULE_COLUMNS = [
    "rule_id",
    "signal_type",
    "relation_type",
    "direction",
    "attenuation",
    "delay_days",
    "max_hops",
    "valid_from",
    "valid_to",
    "available_time",
    "evidence_kind",
    "method",
    "quality_status",
]

EDGE_COLUMNS = [
    "edge_id",
    "source_object_type",
    "source_object_id",
    "target_object_type",
    "target_object_id",
    "relation_type",
    "valid_from",
    "valid_to",
    "available_time",
    "quality_status",
]

OBJECT_COLUMNS = ["object_type", "object_id"]

SNAPSHOT_COLUMNS = [
    "as_of",
    "object_type",
    "object_id",
    "signal_type",
    "concentration",
    "unit",
    "direct_contribution",
    "propagated_contribution",
    "source_event_count",
    "max_hop",
    "quality_status",
]

DEFAULT_SIGNAL_TYPES = [
    {
        "signal_type": "production.activity",
        "display_name": "生产活动",
        "description": "生产或经营活动状态的展示通道；须由证据事件填充。",
        "default_unit": "signal_unit",
        "polarity": "signed",
        "display_color": "#2E7D32",
        "display_channel": "glow",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
    {
        "signal_type": "supply.constraint",
        "display_name": "供给约束",
        "description": "供给受限或缓解的展示通道；不能由行业分类自动推出。",
        "default_unit": "signal_unit",
        "polarity": "signed",
        "display_color": "#EF6C00",
        "display_channel": "halo",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
    {
        "signal_type": "demand.change",
        "display_name": "需求变化",
        "description": "需求变化的展示通道；事件强度须有来源或明确代理标记。",
        "default_unit": "signal_unit",
        "polarity": "signed",
        "display_color": "#1565C0",
        "display_channel": "pulse",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
    {
        "signal_type": "capital.pressure",
        "display_name": "资本压力",
        "description": "资金或融资压力的展示通道；不得把成交量自动解释为具体资金主体。",
        "default_unit": "signal_unit",
        "polarity": "signed",
        "display_color": "#8E24AA",
        "display_channel": "flow",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
    {
        "signal_type": "risk.warning",
        "display_name": "风险警示",
        "description": "风险事件展示通道；不是投资建议或风险概率。",
        "default_unit": "signal_unit",
        "polarity": "nonnegative",
        "display_color": "#C62828",
        "display_channel": "halo",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
    {
        "signal_type": "lifecycle.change",
        "display_name": "生命周期变化",
        "description": "上市、暂停、风险警示、退市等生命周期事件展示通道。",
        "default_unit": "signal_unit",
        "polarity": "signed",
        "display_color": "#455A64",
        "display_channel": "outline",
        "default_half_life_days": pd.NA,
        "evidence_status": "controlled_label_only",
        "quality_status": "empty_until_evidence",
    },
]


@dataclass
class SignalStore:
    signal_types: pd.DataFrame
    events: pd.DataFrame
    rules: pd.DataFrame
    evidence: pd.DataFrame


LIFECYCLE_STATUS_STRENGTH = {
    "status_observed_active": 1.0,
    "status_observed_delisted": -1.0,
}


def lifecycle_status_observations_to_signal_events(
    lifecycle_events: pd.DataFrame,
    *,
    event_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Convert fetch-time listing-status observations into direct signals.

    Historical dates with unknown availability are intentionally rejected.
    The signal becomes effective no earlier than its source record was locally
    available, which prevents archival facts from leaking into older states.
    """
    required = [
        "event_id",
        "listing_id",
        "event_type",
        "event_time",
        "available_time",
        "effective_time",
        "source",
        "evidence_kind",
        "availability_quality",
        "source_status",
    ]
    _require_columns(lifecycle_events, required, "lifecycle_events")
    frame = lifecycle_events.copy()
    if event_ids is not None:
        requested = set(event_ids)
        missing = requested - set(frame["event_id"].astype(str))
        if missing:
            raise ValueError(f"Unknown lifecycle event IDs: {sorted(missing)}")
        frame = frame[frame["event_id"].astype(str).isin(requested)].copy()
    unsupported = set(frame["event_type"].astype(str)) - set(LIFECYCLE_STATUS_STRENGTH)
    if unsupported:
        raise ValueError(
            "Only fetch-time status observations can enter this importer; "
            f"unsupported event types: {sorted(unsupported)}"
        )
    if (frame["availability_quality"].astype(str) != "observed_at_fetch_time").any():
        raise ValueError(
            "Lifecycle signal import requires availability_quality=observed_at_fetch_time"
        )
    normalized = _normalize_time_columns(
        frame, ["event_time", "available_time", "effective_time"]
    )
    if normalized[["event_time", "available_time", "effective_time"]].isna().any().any():
        raise ValueError("Lifecycle observation times are required")

    rows: list[dict[str, Any]] = []
    for _, row in normalized.iterrows():
        source_event_id = str(row["event_id"])
        effective_time = max(row["effective_time"], row["available_time"])
        digest = hashlib.sha256(source_event_id.encode("utf-8")).hexdigest()[:20]
        rows.append(
            {
                "signal_event_id": f"SIGNAL_LIFECYCLE_{digest}",
                "emitter_object_type": "listing",
                "emitter_object_id": str(row["listing_id"]),
                "signal_type": "lifecycle.change",
                "initial_strength": LIFECYCLE_STATUS_STRENGTH[str(row["event_type"])],
                "unit": "signal_unit",
                "event_time": row["event_time"].isoformat(),
                "available_time": row["available_time"].isoformat(),
                "effective_time": effective_time.isoformat(),
                "expires_time": pd.NaT,
                "half_life_days": pd.NA,
                "decay_method": "none",
                "source": row["source"],
                "source_record_id": source_event_id,
                "evidence_kind": row["evidence_kind"],
                "confidence": pd.NA,
                "quality_status": (
                    f"{row['availability_quality']}|{row['source_status']}|"
                    "normalized_binary_lifecycle_state"
                ),
            }
        )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def merge_lifecycle_status_signals(
    existing_events: pd.DataFrame,
    incoming_events: pd.DataFrame,
) -> pd.DataFrame:
    """Idempotently merge lifecycle states and close each state at the next one."""
    _require_columns(existing_events, EVENT_COLUMNS, "existing signal events")
    _require_columns(incoming_events, EVENT_COLUMNS, "incoming signal events")
    incoming_ids = set(incoming_events["signal_event_id"].astype(str))
    result = pd.concat(
        [
            existing_events[
                ~existing_events["signal_event_id"].astype(str).isin(incoming_ids)
            ],
            incoming_events,
        ],
        ignore_index=True,
    )
    lifecycle_mask = (
        (result["emitter_object_type"].astype(str) == "listing")
        & (result["signal_type"].astype(str) == "lifecycle.change")
    )
    lifecycle = result[lifecycle_mask].copy()
    if not lifecycle.empty:
        lifecycle["effective_time"] = pd.to_datetime(
            lifecycle["effective_time"], errors="raise", utc=True, format="mixed"
        )
        lifecycle = lifecycle.sort_values(
            ["emitter_object_id", "effective_time", "signal_event_id"], kind="stable"
        )
        lifecycle["expires_time"] = lifecycle.groupby("emitter_object_id")[
            "effective_time"
        ].shift(-1)
        result = pd.concat(
            [result[~lifecycle_mask], lifecycle[EVENT_COLUMNS]], ignore_index=True
        )
    return result[EVENT_COLUMNS].sort_values(
        ["available_time", "signal_event_id"], kind="stable"
    ).reset_index(drop=True)


def merge_signal_events(
    existing_events: pd.DataFrame,
    incoming_events: pd.DataFrame,
) -> pd.DataFrame:
    """Idempotently merge generic signal events by stable signal_event_id."""
    _require_columns(existing_events, EVENT_COLUMNS, "existing signal events")
    _require_columns(incoming_events, EVENT_COLUMNS, "incoming signal events")
    incoming_ids = set(incoming_events["signal_event_id"].astype(str))
    return pd.concat(
        [
            existing_events[
                ~existing_events["signal_event_id"].astype(str).isin(incoming_ids)
            ],
            incoming_events,
        ],
        ignore_index=True,
    )[EVENT_COLUMNS].sort_values(
        ["available_time", "signal_event_id"], kind="stable"
    ).reset_index(drop=True)


def approved_production_mappings_to_signal_bundle(
    business_activities: pd.DataFrame,
    products: pd.DataFrame,
    mappings: pd.DataFrame,
    *,
    mapping_ids: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert reviewed producer mappings into direct binary activity signals."""
    activity_required = [
        "activity_id",
        "company_id",
        "activity_text",
        "available_time",
        "source",
        "source_record_id",
    ]
    product_required = ["product_id", "canonical_name"]
    mapping_required = [
        "mapping_id",
        "activity_id",
        "company_id",
        "product_id",
        "role",
        "evidence_quote",
        "available_time",
        "review_status",
        "reviewer",
        "reviewed_at",
        "confidence",
    ]
    _require_columns(business_activities, activity_required, "business_activities")
    _require_columns(products, product_required, "products")
    _require_columns(mappings, mapping_required, "activity_product_candidates")
    requested = set(mapping_ids)
    selected = mappings[mappings["mapping_id"].astype(str).isin(requested)].copy()
    missing = requested - set(selected["mapping_id"].astype(str))
    if missing:
        raise ValueError(f"Unknown activity-product mapping IDs: {sorted(missing)}")
    if (selected["review_status"].astype(str) != "approved").any():
        raise ValueError("Production signals require approved activity-product mappings")
    if (selected["role"].astype(str) != "producer").any():
        raise ValueError("production.activity currently accepts only role=producer")

    activities = business_activities.set_index("activity_id", drop=False)
    product_lookup = products.set_index("product_id", drop=False)
    event_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for _, mapping in selected.iterrows():
        activity_id = str(mapping["activity_id"])
        product_id = str(mapping["product_id"])
        if activity_id not in activities.index:
            raise ValueError(f"Mapping references unknown activity_id: {activity_id}")
        if product_id not in product_lookup.index:
            raise ValueError(f"Mapping references unknown product_id: {product_id}")
        activity = activities.loc[activity_id]
        product = product_lookup.loc[product_id]
        quote = str(mapping["evidence_quote"])
        activity_text = str(activity["activity_text"])
        if not quote or quote not in activity_text:
            raise ValueError(
                f"Mapping evidence_quote is not present in activity_text: {mapping['mapping_id']}"
            )
        reviewed_at = _as_utc(mapping["reviewed_at"])
        mapping_available = _as_utc(mapping["available_time"])
        activity_available = _as_utc(activity["available_time"])
        effective_time = max(reviewed_at, mapping_available, activity_available)
        mapping_id = str(mapping["mapping_id"])
        event_digest = hashlib.sha256(mapping_id.encode("utf-8")).hexdigest()[:20]
        signal_event_id = f"SIGNAL_PRODUCTION_{event_digest}"
        evidence_digest = hashlib.sha256(
            f"production-evidence:{mapping_id}".encode("utf-8")
        ).hexdigest()[:20]
        product_name = str(product["canonical_name"])
        event_rows.append(
            {
                "signal_event_id": signal_event_id,
                "emitter_object_type": "company",
                "emitter_object_id": str(mapping["company_id"]),
                "signal_type": "production.activity",
                "initial_strength": 1.0,
                "unit": "signal_unit",
                "event_time": activity_available.isoformat(),
                "available_time": reviewed_at.isoformat(),
                "effective_time": effective_time.isoformat(),
                "expires_time": pd.NaT,
                "half_life_days": pd.NA,
                "decay_method": "none",
                "source": f"{activity['source']} + explicit project review",
                "source_record_id": mapping_id,
                "evidence_kind": "human_reviewed_observation",
                "confidence": pd.NA,
                "quality_status": (
                    "human_reviewed_exact_text_match|raw_quantity_not_reported|"
                    "normalized_binary_activity_presence"
                ),
            }
        )
        evidence_rows.append(
            {
                "evidence_id": f"SIGNAL_EVIDENCE_{evidence_digest}",
                "signal_event_id": signal_event_id,
                "source": str(activity["source"]),
                "source_record_id": mapping_id,
                "claim_type": "approved_production_activity",
                "claim_value": "activity_presence",
                "dimension_type": "product",
                "dimension_id": product_id,
                "raw_numeric_value": pd.NA,
                "raw_unit": "not_reported",
                "raw_text": quote,
                "event_time": activity_available.isoformat(),
                "available_time": reviewed_at.isoformat(),
                "source_locator": "data/industry_network/a_share/activity_product_candidates.csv",
                "evidence_kind": "human_reviewed_observation",
                "verification_method": (
                    f"exact quote match; role=producer; product={product_name}; "
                    f"reviewer={mapping['reviewer']}; reviewed_at={reviewed_at.isoformat()}"
                ),
                "quality_status": str(mapping["confidence"]),
            }
        )
    return (
        pd.DataFrame(event_rows, columns=EVENT_COLUMNS),
        pd.DataFrame(evidence_rows, columns=EVIDENCE_COLUMNS),
    )


def szse_a_share_list_evidence(
    payload: Any,
    *,
    signal_event_id: str,
    symbol: str,
    expected_name: str,
    fetched_at: str | pd.Timestamp,
    source_locator: str,
) -> pd.DataFrame:
    """Create exact-match evidence from the official SZSE A-share list response."""
    if not isinstance(payload, list):
        raise ValueError("SZSE response must be a list of report tabs")
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for block in payload:
        if not isinstance(block, dict):
            continue
        metadata = block.get("metadata") or {}
        for row in block.get("data") or []:
            if str(row.get("agdm", "")).strip() == symbol:
                matches.append((metadata, row))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one SZSE A-share row for {symbol}, found {len(matches)}")
    metadata, row = matches[0]
    observed_name = re.sub(r"<[^>]+>", "", str(row.get("agjc", ""))).strip()
    if observed_name != expected_name:
        raise ValueError(
            f"SZSE name mismatch for {symbol}: {observed_name!r} != {expected_name!r}"
        )
    list_date_text = str(metadata.get("subname", "")).strip()
    list_date = pd.to_datetime(list_date_text, errors="coerce")
    if pd.isna(list_date):
        raise ValueError("SZSE A-share list date is missing or invalid")
    list_time = pd.Timestamp(list_date).tz_localize("Asia/Shanghai")
    available_time = _as_utc(fetched_at)
    source_record_id = f"SZSE_A_SHARE_LIST_1110_{list_time.date()}_{symbol}"
    digest = hashlib.sha256(source_record_id.encode("utf-8")).hexdigest()[:20]
    return pd.DataFrame(
        [
            {
                "evidence_id": f"SIGNAL_EVIDENCE_{digest}",
                "signal_event_id": signal_event_id,
                "source": "Shenzhen Stock Exchange official A-share list",
                "source_record_id": source_record_id,
                "claim_type": "official_listing_presence",
                "claim_value": "listed_on_a_share_list",
                "dimension_type": "security",
                "dimension_id": symbol,
                "raw_numeric_value": pd.NA,
                "raw_unit": "not_applicable",
                "raw_text": observed_name,
                "event_time": list_time.isoformat(),
                "available_time": available_time.isoformat(),
                "source_locator": source_locator,
                "evidence_kind": "official_observation",
                "verification_method": (
                    f"exact agdm={symbol}; exact name={expected_name}; "
                    f"board={row.get('bk')}; listing_date={row.get('agssrq')}"
                ),
                "quality_status": "official_source_exact_code_and_name_match",
            }
        ],
        columns=EVIDENCE_COLUMNS,
    )


def merge_signal_evidence(
    existing_evidence: pd.DataFrame,
    incoming_evidence: pd.DataFrame,
    signal_events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Idempotently merge evidence and annotate corroborated signal events."""
    _require_columns(existing_evidence, EVIDENCE_COLUMNS, "existing signal evidence")
    _require_columns(incoming_evidence, EVIDENCE_COLUMNS, "incoming signal evidence")
    _require_columns(signal_events, EVENT_COLUMNS, "signal events")
    incoming_ids = set(incoming_evidence["evidence_id"].astype(str))
    merged = pd.concat(
        [
            existing_evidence[
                ~existing_evidence["evidence_id"].astype(str).isin(incoming_ids)
            ],
            incoming_evidence,
        ],
        ignore_index=True,
    )
    validate_signal_evidence(merged, signal_events)
    updated_events = signal_events.copy()
    confirmed_ids = set(
        merged.loc[
            (merged["claim_type"] == "official_listing_presence")
            & (merged["quality_status"] == "official_source_exact_code_and_name_match"),
            "signal_event_id",
        ].astype(str)
    )
    for index, row in updated_events.iterrows():
        if str(row["signal_event_id"]) not in confirmed_ids:
            continue
        parts = [part for part in str(row["quality_status"]).split("|") if part]
        marker = "official_listing_presence_confirmed"
        if marker not in parts:
            parts.append(marker)
        updated_events.at[index, "quality_status"] = "|".join(parts)
    return (
        merged[EVIDENCE_COLUMNS].sort_values(
            ["available_time", "evidence_id"], kind="stable"
        ).reset_index(drop=True),
        updated_events[EVENT_COLUMNS],
    )


def validate_signal_types(signal_types: pd.DataFrame) -> None:
    _require_columns(signal_types, SIGNAL_TYPE_COLUMNS, "signal_types")
    if signal_types["signal_type"].duplicated().any():
        raise ValueError("signal_type must be unique")
    if signal_types["signal_type"].astype(str).isin({"", "nan"}).any():
        raise ValueError("signal_type cannot be empty")


def validate_signal_events(events: pd.DataFrame, signal_types: pd.DataFrame | None = None) -> None:
    _require_columns(events, EVENT_COLUMNS, "signal_events")
    _validate_object_columns(events, "emitter_object_type", "emitter_object_id")
    _validate_times(events, ["event_time", "available_time", "effective_time", "expires_time"], "signal_events")
    if not events.empty and events[["event_time", "available_time", "effective_time"]].isna().any().any():
        raise ValueError("event_time, available_time and effective_time are required")
    if events["signal_event_id"].duplicated().any():
        raise ValueError("signal_event_id must be unique")
    strength = pd.to_numeric(events["initial_strength"], errors="coerce")
    if strength.isna().any() or ~strength.map(math.isfinite).all():
        raise ValueError("initial_strength must be finite numbers")
    half_life = pd.to_numeric(events["half_life_days"], errors="coerce")
    decays = events["decay_method"].fillna("exponential_half_life").astype(str)
    if ((decays == "exponential_half_life") & (half_life <= 0)).any():
        raise ValueError("exponential_half_life events require half_life_days > 0")
    if not events.empty:
        normalized = _normalize_time_columns(
            events, ["event_time", "available_time", "effective_time", "expires_time"]
        )
        if (normalized["effective_time"] < normalized["event_time"]).any():
            raise ValueError("effective_time cannot precede event_time")
        if (normalized["expires_time"].notna() & (normalized["expires_time"] <= normalized["effective_time"])).any():
            raise ValueError("expires_time must be after effective_time")
    if signal_types is not None:
        validate_signal_types(signal_types)
        allowed = set(signal_types["signal_type"])
        unknown = set(events["signal_type"]) - allowed
        if unknown:
            raise ValueError(f"Unknown signal types: {sorted(unknown)}")
        units = signal_types.set_index("signal_type")["default_unit"]
        polarity = signal_types.set_index("signal_type")["polarity"]
        for _, row in events.iterrows():
            expected = units.get(row["signal_type"])
            if pd.isna(row["unit"]) or str(row["unit"]).strip() == "":
                raise ValueError("signal event unit is required")
            if expected is not None and row["unit"] != expected:
                raise ValueError(f"Unit mismatch for {row['signal_type']}: {row['unit']} != {expected}")
            if polarity.get(row["signal_type"]) == "nonnegative" and float(row["initial_strength"]) < 0:
                raise ValueError(f"Negative strength is not allowed for nonnegative signal {row['signal_type']}")


def validate_signal_evidence(
    evidence: pd.DataFrame,
    signal_events: pd.DataFrame | None = None,
) -> None:
    _require_columns(evidence, EVIDENCE_COLUMNS, "signal_event_evidence")
    if evidence["evidence_id"].duplicated().any():
        raise ValueError("evidence_id must be unique")
    _validate_times(evidence, ["event_time", "available_time"], "signal_event_evidence")
    if not evidence.empty and evidence[["event_time", "available_time"]].isna().any().any():
        raise ValueError("signal evidence event_time and available_time are required")
    raw_values = pd.to_numeric(evidence["raw_numeric_value"], errors="coerce")
    invalid_raw = evidence["raw_numeric_value"].notna() & raw_values.isna()
    if invalid_raw.any():
        raise ValueError("raw_numeric_value must be numeric when reported")
    if (
        evidence["raw_numeric_value"].isna()
        & evidence["raw_unit"].astype(str).eq("")
    ).any():
        raise ValueError("raw_unit must state why a numeric value is absent")
    if signal_events is not None:
        _require_columns(signal_events, EVENT_COLUMNS, "signal events")
        unknown = set(evidence["signal_event_id"].astype(str)) - set(
            signal_events["signal_event_id"].astype(str)
        )
        if unknown:
            raise ValueError(f"Signal evidence references unknown events: {sorted(unknown)}")


def validate_transmission_rules(rules: pd.DataFrame, signal_types: pd.DataFrame | None = None) -> None:
    _require_columns(rules, RULE_COLUMNS, "transmission_rules")
    if rules["rule_id"].duplicated().any():
        raise ValueError("rule_id must be unique")
    _validate_times(rules, ["valid_from", "valid_to", "available_time"], "transmission_rules")
    if not rules.empty and rules["available_time"].isna().any():
        raise ValueError("transmission rule available_time is required")
    attenuation = pd.to_numeric(rules["attenuation"], errors="coerce")
    delay = pd.to_numeric(rules["delay_days"], errors="coerce")
    hops = pd.to_numeric(rules["max_hops"], errors="coerce")
    if attenuation.isna().any() or ((attenuation < 0) | (attenuation > 1)).any():
        raise ValueError("attenuation must be between 0 and 1")
    if delay.isna().any() or (delay < 0).any():
        raise ValueError("delay_days must be non-negative")
    if hops.isna().any() or (hops < 1).any() or (hops % 1 != 0).any():
        raise ValueError("max_hops must be a positive integer")
    if ~rules["direction"].astype(str).isin({"forward", "reverse", "bidirectional"}).all():
        raise ValueError("direction must be forward, reverse, or bidirectional")
    if signal_types is not None:
        validate_signal_types(signal_types)
        unknown = set(rules["signal_type"]) - set(signal_types["signal_type"])
        if unknown:
            raise ValueError(f"Unknown signal types in rules: {sorted(unknown)}")


def validate_network_edges(edges: pd.DataFrame) -> None:
    _require_columns(edges, EDGE_COLUMNS, "network_edges")
    if edges["edge_id"].duplicated().any():
        raise ValueError("edge_id must be unique")
    _validate_object_columns(edges, "source_object_type", "source_object_id")
    _validate_object_columns(edges, "target_object_type", "target_object_id")
    _validate_times(edges, ["valid_from", "valid_to", "available_time"], "network_edges")
    if not edges.empty and edges["available_time"].isna().any():
        raise ValueError("network edge available_time is required")


def build_signal_snapshot(
    events: pd.DataFrame,
    rules: pd.DataFrame,
    network_edges: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
    signal_types: pd.DataFrame,
    objects: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute a point-in-time signal field without future-information leakage."""
    validate_signal_types(signal_types)
    validate_signal_events(events, signal_types)
    validate_transmission_rules(rules, signal_types)
    validate_network_edges(network_edges)
    cutoff = _as_utc(as_of)
    event_frame = _normalize_time_columns(events, ["event_time", "available_time", "effective_time", "expires_time"])
    rule_frame = _normalize_time_columns(rules, ["valid_from", "valid_to", "available_time"])
    edge_frame = _normalize_time_columns(network_edges, ["valid_from", "valid_to", "available_time"])
    event_frame = event_frame[event_frame["available_time"] <= cutoff].copy()
    rule_frame = rule_frame[rule_frame["available_time"] <= cutoff].copy()
    edge_frame = edge_frame[edge_frame["available_time"] <= cutoff].copy()
    allowed_types = list(signal_types["signal_type"])

    if objects is None:
        object_frame = _objects_from_frames(event_frame, edge_frame)
    else:
        _require_columns(objects, OBJECT_COLUMNS, "objects")
        object_frame = objects[OBJECT_COLUMNS].drop_duplicates().copy()
    _validate_object_columns(object_frame, "object_type", "object_id")

    rows: list[dict[str, Any]] = []
    for _, event in event_frame.iterrows():
        if pd.isna(event["effective_time"]) or event["effective_time"] > cutoff:
            continue
        if pd.notna(event["expires_time"]) and event["expires_time"] <= cutoff:
            continue
        source = (event["emitter_object_type"], str(event["emitter_object_id"]))
        initial = float(event["initial_strength"])
        decay_method = str(event.get("decay_method") or "exponential_half_life")
        half_life = float(event["half_life_days"]) if pd.notna(event["half_life_days"]) else None
        paths: dict[tuple[str, str], tuple[float, int, str]] = {source: (1.0, 0, "direct")}
        queue = [(source[0], source[1], 1.0, 0, event["effective_time"])]
        while queue:
            current_type, current_id, multiplier, hop, arrival = queue.pop(0)
            if hop > 0 and arrival > cutoff:
                continue
            candidates = _outgoing_edges(edge_frame, current_type, current_id, arrival, cutoff)
            for _, edge in candidates.iterrows():
                matching = rule_frame[
                    (rule_frame["signal_type"] == event["signal_type"])
                    & (rule_frame["relation_type"] == edge["relation_type"])
                ]
                for _, rule in matching.iterrows():
                    if hop >= int(rule["max_hops"]):
                        continue
                    target_type, target_id = _rule_target(edge, current_type, current_id, str(rule["direction"]))
                    if target_type is None:
                        continue
                    departure = max(arrival, rule["available_time"], edge["available_time"])
                    if pd.notna(rule["valid_from"]):
                        departure = max(departure, rule["valid_from"])
                    if pd.notna(edge["valid_from"]):
                        departure = max(departure, edge["valid_from"])
                    arrival_next = departure + pd.Timedelta(days=float(rule["delay_days"]))
                    if arrival_next > cutoff:
                        continue
                    if pd.notna(rule["valid_to"]) and arrival_next > rule["valid_to"]:
                        continue
                    if pd.notna(edge["valid_to"]) and arrival_next > edge["valid_to"]:
                        continue
                    next_multiplier = multiplier * float(rule["attenuation"])
                    key = (target_type, target_id)
                    previous = paths.get(key)
                    if previous is not None and abs(next_multiplier) <= abs(previous[0]):
                        continue
                    paths[key] = (next_multiplier, hop + 1, "propagated")
                    queue.append((target_type, target_id, next_multiplier, hop + 1, arrival_next))

        elapsed_days = max(0.0, (cutoff - event["effective_time"]).total_seconds() / 86400.0)
        decay = 1.0
        if decay_method == "exponential_half_life":
            if not half_life or half_life <= 0:
                raise ValueError("half_life_days must be positive for exponential decay")
            decay = 0.5 ** (elapsed_days / half_life)
        elif decay_method not in {"none", "step"}:
            raise ValueError(f"Unsupported decay_method: {decay_method}")
        for (object_type, object_id), (multiplier, max_hop, path_kind) in paths.items():
            contribution = initial * decay * multiplier
            if contribution == 0:
                continue
            rows.append({
                "object_type": object_type,
                "object_id": object_id,
                "signal_type": event["signal_type"],
                "contribution": contribution,
                "direct": contribution if path_kind == "direct" else 0.0,
                "propagated": contribution if path_kind == "propagated" else 0.0,
                "event_id": event["signal_event_id"],
                "hop": max_hop,
            })

    contribution_frame = pd.DataFrame(rows)
    type_units = signal_types.set_index("signal_type")["default_unit"].to_dict()
    if contribution_frame.empty:
        contribution_frame = pd.DataFrame(columns=["object_type", "object_id", "signal_type", "contribution", "direct", "propagated", "event_id", "hop"])
    if contribution_frame.empty:
        aggregate = pd.DataFrame(
            columns=[
                "object_type", "object_id", "signal_type", "concentration",
                "direct_contribution", "propagated_contribution", "source_event_count", "max_hop",
            ]
        )
    else:
        grouped = contribution_frame.groupby(["object_type", "object_id", "signal_type"], dropna=False)
        aggregate = grouped.agg(
            concentration=("contribution", "sum"),
            direct_contribution=("direct", "sum"),
            propagated_contribution=("propagated", "sum"),
            source_event_count=("event_id", "nunique"),
            max_hop=("hop", "max"),
        ).reset_index()
    if objects is not None or not object_frame.empty:
        dense = object_frame.assign(_key=1).merge(
            signal_types[["signal_type"]].assign(_key=1), on="_key", how="outer"
        ).drop(columns="_key")
        aggregate = dense.merge(aggregate, on=["object_type", "object_id", "signal_type"], how="left")
    aggregate["concentration"] = aggregate["concentration"].fillna(0.0)
    aggregate["direct_contribution"] = aggregate["direct_contribution"].fillna(0.0)
    aggregate["propagated_contribution"] = aggregate["propagated_contribution"].fillna(0.0)
    aggregate["source_event_count"] = aggregate["source_event_count"].fillna(0).astype(int)
    aggregate["max_hop"] = aggregate["max_hop"].fillna(0).astype(int)
    aggregate["unit"] = aggregate["signal_type"].map(type_units).fillna("signal_unit")
    aggregate["as_of"] = cutoff.isoformat()
    if aggregate.empty:
        aggregate["quality_status"] = pd.Series(dtype="object")
    else:
        aggregate["quality_status"] = aggregate.apply(_quality_status, axis=1)
    return aggregate[SNAPSHOT_COLUMNS].sort_values(["object_type", "object_id", "signal_type"], kind="stable").reset_index(drop=True)


def network_objects_and_edges(tables: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert explicit v2 network tables into display objects and typed edges."""
    objects: list[dict[str, str]] = []
    edges: list[dict[str, Any]] = []

    def add_objects(object_type: str, frame: pd.DataFrame, id_column: str) -> None:
        for value in frame.get(id_column, pd.Series(dtype=object)).dropna().astype(str).unique():
            objects.append({"object_type": object_type, "object_id": value})

    add_objects("company", tables.companies, "company_id")
    add_objects("listing", tables.listings, "listing_id")
    add_objects("industry", tables.industries, "industry_id")
    add_objects("product", tables.products, "product_id")

    def add_edge(source_type: str, source_id: Any, target_type: str, target_id: Any, relation: str, row: pd.Series | None = None) -> None:
        if pd.isna(source_id) or pd.isna(target_id):
            return
        row = row if row is not None else pd.Series(dtype=object)
        edges.append({
            "edge_id": f"{relation}:{source_type}:{source_id}:{target_type}:{target_id}",
            "source_object_type": source_type,
            "source_object_id": str(source_id),
            "target_object_type": target_type,
            "target_object_id": str(target_id),
            "relation_type": relation,
            "valid_from": row.get("valid_from", "1900-01-01T00:00:00Z"),
            "valid_to": row.get("valid_to", pd.NaT),
            "available_time": row.get("available_time", "1900-01-01T00:00:00Z"),
            "quality_status": row.get("source_status", row.get("review_status", "network_evidence")),
        })

    for _, row in tables.listings.iterrows():
        add_edge("listing", row.get("listing_id"), "company", row.get("company_id"), "listing_claim_on_company", row)
    for _, row in tables.memberships.iterrows():
        add_edge("company", row.get("company_id"), "industry", row.get("industry_id"), "classified_as_industry", row)
    for _, row in tables.relations.iterrows():
        add_edge("company", row.get("source_company_id"), "company", row.get("target_company_id"), str(row.get("relation_type")), row)
    for _, row in tables.activity_product_candidates.iterrows():
        if str(row.get("review_status")) != "approved":
            continue
        role = str(row.get("role"))
        add_edge("company", row.get("company_id"), "product", row.get("product_id"), role, row)
    return pd.DataFrame(objects, columns=OBJECT_COLUMNS).drop_duplicates(), pd.DataFrame(edges, columns=EDGE_COLUMNS).drop_duplicates("edge_id")


def initialize_signal_store(directory: str | Path, *, overwrite: bool = False) -> SignalStore:
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    signal_types = pd.DataFrame(DEFAULT_SIGNAL_TYPES, columns=SIGNAL_TYPE_COLUMNS)
    events = pd.DataFrame(columns=EVENT_COLUMNS)
    rules = pd.DataFrame(columns=RULE_COLUMNS)
    evidence = pd.DataFrame(columns=EVIDENCE_COLUMNS)
    for name, frame in [
        ("signal_types.csv", signal_types),
        ("signal_events.csv", events),
        ("transmission_rules.csv", rules),
        ("signal_event_evidence.csv", evidence),
    ]:
        path = destination / name
        if path.exists() and not overwrite:
            continue
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    meta = {
        "schema_version": SIGNAL_SCHEMA_VERSION,
        "created_at_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "signal_types": list(signal_types["signal_type"]),
        "known_limits": [
            "signal types are controlled display labels; each non-zero event still requires evidence",
            "no signal propagates without both an explicit network edge and transmission rule",
            "display colours are defaults, not measured attributes",
        ],
    }
    meta_path = destination / "signal_store.meta.json"
    if overwrite or not meta_path.exists():
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return load_signal_store(destination)


def load_signal_store(directory: str | Path) -> SignalStore:
    source = Path(directory)
    signal_types = pd.read_csv(source / "signal_types.csv")
    events = pd.read_csv(source / "signal_events.csv")
    rules = pd.read_csv(source / "transmission_rules.csv")
    evidence_path = source / "signal_event_evidence.csv"
    evidence = (
        pd.read_csv(
            evidence_path,
            dtype={
                "evidence_id": "string",
                "signal_event_id": "string",
                "source_record_id": "string",
                "dimension_id": "string",
            },
        )
        if evidence_path.exists()
        else pd.DataFrame(columns=EVIDENCE_COLUMNS)
    )
    for column in EVIDENCE_COLUMNS:
        if column not in evidence.columns:
            evidence[column] = pd.NA
    if events.empty:
        events = pd.DataFrame(columns=EVENT_COLUMNS)
    if rules.empty:
        rules = pd.DataFrame(columns=RULE_COLUMNS)
    if evidence.empty:
        evidence = pd.DataFrame(columns=EVIDENCE_COLUMNS)
    validate_signal_types(signal_types)
    validate_signal_events(events, signal_types)
    validate_transmission_rules(rules, signal_types)
    evidence = evidence[EVIDENCE_COLUMNS]
    validate_signal_evidence(evidence, events)
    return SignalStore(signal_types, events, rules, evidence)


def write_signal_snapshot(snapshot: pd.DataFrame, output_path: str | Path) -> None:
    _require_columns(snapshot, SNAPSHOT_COLUMNS, "signal snapshot")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(destination, index=False, encoding="utf-8-sig")


def _quality_status(row: pd.Series) -> str:
    if int(row["source_event_count"]) == 0:
        return "no_signal"
    if abs(float(row["propagated_contribution"])) > 0:
        return "includes_propagated_signal"
    return "direct_signal_only"


def _outgoing_edges(edges: pd.DataFrame, current_type: str, current_id: str, at: pd.Timestamp, cutoff: pd.Timestamp) -> pd.DataFrame:
    outgoing = edges[(edges["source_object_type"] == current_type) & (edges["source_object_id"].astype(str) == current_id)].copy()
    reverse = edges[(edges["target_object_type"] == current_type) & (edges["target_object_id"].astype(str) == current_id)].copy()
    if outgoing.empty and reverse.empty:
        return pd.DataFrame(columns=list(edges.columns) + ["_reverse"])
    outgoing["_reverse"] = False
    reverse["_reverse"] = True
    result = pd.concat([outgoing, reverse], ignore_index=True)
    valid = (result["valid_from"].isna() | (result["valid_from"] <= cutoff)) & (result["valid_to"].isna() | (result["valid_to"] >= at))
    return result[valid]


def _rule_target(edge: pd.Series, current_type: str, current_id: str, direction: str) -> tuple[str | None, str | None]:
    reverse = bool(edge.get("_reverse", False))
    if direction == "forward" and reverse:
        return None, None
    if direction == "reverse" and not reverse:
        return None, None
    if reverse:
        return str(edge["source_object_type"]), str(edge["source_object_id"])
    return str(edge["target_object_type"]), str(edge["target_object_id"])


def _objects_from_frames(events: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in events.iterrows():
        rows.append({"object_type": row["emitter_object_type"], "object_id": str(row["emitter_object_id"])})
    for _, row in edges.iterrows():
        rows.extend([
            {"object_type": row["source_object_type"], "object_id": str(row["source_object_id"])},
            {"object_type": row["target_object_type"], "object_id": str(row["target_object_id"])},
        ])
    return pd.DataFrame(rows, columns=OBJECT_COLUMNS).drop_duplicates()


def _validate_object_columns(frame: pd.DataFrame, type_column: str, id_column: str) -> None:
    if frame[type_column].isna().any() or ~frame[type_column].astype(str).isin(OBJECT_TYPES).all():
        raise ValueError(f"{type_column} contains unsupported object type")
    if frame[id_column].isna().any() or (frame[id_column].astype(str).str.strip() == "").any():
        raise ValueError(f"{id_column} cannot be empty")


def _validate_times(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    for column in columns:
        parsed = pd.to_datetime(frame[column], errors="coerce", utc=True, format="mixed")
        if parsed.isna().any() and not frame[column].isna().all():
            raise ValueError(f"{name}.{column} contains invalid timestamps")


def _normalize_time_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(result[column], errors="coerce", utc=True, format="mixed")
    return result


def _require_columns(frame: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")


def _as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    return timestamp.tz_convert(timezone.utc)
