"""Contracts and validation helpers for capital-control attribution.

The module deliberately keeps observed flow events separate from probabilistic
attribution.  A quote or turnover record can describe *what traded*, but it
does not identify the beneficial owner or decision maker behind the trade.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd


CAPITAL_CONTROL_SCHEMA_VERSION = "capital_control_distribution_v1"

FLOW_EVENT_COLUMNS = [
    "schema_version",
    "flow_event_id",
    "instrument_id",
    "market",
    "event_time",
    "available_time",
    "availability_policy",
    "flow_measure",
    "side",
    "observed_amount",
    "amount_unit",
    "source",
    "source_record_id",
    "evidence_kind",
    "method",
    "quality_status",
]

CONTROLLER_COLUMNS = [
    "controller_id",
    "controller_class",
    "display_name",
    "identity_scope",
    "identity_basis",
    "source",
    "source_record_id",
    "available_time",
    "quality_status",
]

CAPITAL_POOL_COLUMNS = [
    "capital_pool_id",
    "pool_type",
    "display_name",
    "currency",
    "source",
    "source_record_id",
    "available_time",
    "quality_status",
]

CONTROL_RELATION_COLUMNS = [
    "relation_id",
    "capital_pool_id",
    "controller_id",
    "control_role",
    "valid_from",
    "valid_to",
    "control_share",
    "available_time",
    "evidence_kind",
    "source",
    "source_record_id",
    "confidence",
    "quality_status",
]

DISTRIBUTION_COLUMNS = [
    "schema_version",
    "distribution_id",
    "flow_event_id",
    "instrument_id",
    "event_time",
    "available_time",
    "controller_id",
    "controller_class",
    "control_role",
    "probability",
    "estimated_signed_amount",
    "amount_unit",
    "probability_status",
    "probability_method",
    "evidence_kind",
    "evidence_ids",
    "source",
    "quality_status",
]

KNOWN_CONTROLLER_CLASSES = {
    "household",
    "public_fund",
    "private_fund",
    "insurance",
    "social_security",
    "state_owned",
    "corporate_treasury",
    "foreign_investor",
    "controlling_shareholder",
    "fund_management_company",
    "fund_manager",
    "broker_dealer",
    "bank",
    "custodian_nominee",
    "market_maker",
    "other",
    "unknown",
}

KNOWN_CONTROL_ROLES = {
    "beneficial_owner",
    "mandate_decision_maker",
    "trader_executor",
    "custodian_nominee",
    "inferred_group",
}


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")


def validate_flow_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a copy of observed flow events.

    This function does not infer a controller.  An event may therefore be
    perfectly valid while its later attribution remains entirely unknown.
    """

    _require_columns(frame, FLOW_EVENT_COLUMNS, "flow events")
    result = frame.copy()
    if result["flow_event_id"].duplicated().any():
        raise ValueError("flow_event_id must be unique")
    if (result["observed_amount"] < 0).any():
        raise ValueError("observed_amount must be non-negative")
    if not result["evidence_kind"].isin({"observation", "derived", "proxy"}).all():
        raise ValueError("flow event evidence_kind must be observation, derived, or proxy")
    return result


def validate_control_relations(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate time-aware pool-to-controller relationships."""

    _require_columns(frame, CONTROL_RELATION_COLUMNS, "control relations")
    result = frame.copy()
    if result["relation_id"].duplicated().any():
        raise ValueError("relation_id must be unique")
    invalid_roles = set(result["control_role"].dropna()) - KNOWN_CONTROL_ROLES
    if invalid_roles:
        raise ValueError(f"Unsupported control_role values: {sorted(invalid_roles)}")
    share = pd.to_numeric(result["control_share"], errors="coerce")
    if ((share.notna()) & ((share < 0) | (share > 1))).any():
        raise ValueError("control_share must be between 0 and 1 when known")
    return result


def validate_distribution(
    frame: pd.DataFrame,
    *,
    tolerance: float = 1e-9,
) -> pd.DataFrame:
    """Validate a conditional controller probability distribution.

    Probabilities must sum to one for every flow event.  The explicit
    ``unknown`` controller is required whenever no controller is identified;
    this prevents the table from silently converting missing evidence into a
    named person's probability.
    """

    _require_columns(frame, DISTRIBUTION_COLUMNS, "capital-control distribution")
    result = frame.copy()
    if result.empty:
        return result
    if result["distribution_id"].duplicated().any():
        raise ValueError("distribution_id must be unique")
    if not result["schema_version"].eq(CAPITAL_CONTROL_SCHEMA_VERSION).all():
        raise ValueError("Unexpected capital-control schema_version")
    probability = pd.to_numeric(result["probability"], errors="coerce")
    if probability.isna().any() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("probability must be numeric and between 0 and 1")
    sums = probability.groupby(result["flow_event_id"]).sum()
    if not ((sums - 1).abs() <= tolerance).all():
        bad = sums[(sums - 1).abs() > tolerance].to_dict()
        raise ValueError(f"Probabilities must sum to 1 per flow event: {bad}")
    invalid_classes = set(result["controller_class"].dropna()) - KNOWN_CONTROLLER_CLASSES
    if invalid_classes:
        raise ValueError(f"Unsupported controller_class values: {sorted(invalid_classes)}")
    invalid_roles = set(result["control_role"].dropna()) - KNOWN_CONTROL_ROLES
    if invalid_roles:
        raise ValueError(f"Unsupported control_role values: {sorted(invalid_roles)}")
    if (result["controller_class"] == "unknown").any():
        unknown_rows = result[result["controller_class"] == "unknown"]
        if not unknown_rows["controller_id"].eq("CONTROLLER_UNKNOWN").all():
            raise ValueError("unknown controller_class must use CONTROLLER_UNKNOWN")
    return result


def expected_attribution(
    flow_events: pd.DataFrame,
    distribution: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate expected signed amount from observed amount and probabilities."""

    events = validate_flow_events(flow_events)
    probabilities = validate_distribution(distribution)
    _require_columns(events, ["flow_event_id", "side"], "flow events")
    joined = probabilities.merge(
        events[["flow_event_id", "observed_amount", "amount_unit", "side"]],
        on="flow_event_id",
        how="left",
        validate="many_to_one",
    )
    if joined["observed_amount"].isna().any():
        raise ValueError("Every distribution row must reference a known flow event")
    sign = joined["side"].map({"buy": 1.0, "sell": -1.0, "net_buy": 1.0, "net_sell": -1.0}).fillna(0.0)
    joined["expected_signed_amount"] = (
        joined["observed_amount"] * joined["probability"] * sign
    )
    return joined


def distribution_as_of(
    frame: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
) -> pd.DataFrame:
    """Return only attribution rows available by a historical decision time."""

    probabilities = validate_distribution(frame)
    if probabilities.empty:
        return probabilities
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    available = pd.to_datetime(
        probabilities["available_time"], errors="coerce", utc=True, format="mixed"
    )
    return probabilities[available.notna() & available.le(cutoff)].reset_index(drop=True)


def unknown_only_distribution(flow_events: pd.DataFrame) -> pd.DataFrame:
    """Create a conservative starting distribution with all attribution unknown."""

    events = validate_flow_events(flow_events)
    rows = []
    for row in events.itertuples(index=False):
        rows.append(
            {
                "schema_version": CAPITAL_CONTROL_SCHEMA_VERSION,
                "distribution_id": f"DIST_UNKNOWN_{row.flow_event_id}",
                "flow_event_id": row.flow_event_id,
                "instrument_id": row.instrument_id,
                "event_time": row.event_time,
                "available_time": row.available_time,
                "controller_id": "CONTROLLER_UNKNOWN",
                "controller_class": "unknown",
                "control_role": "inferred_group",
                "probability": 1.0,
                "estimated_signed_amount": None,
                "amount_unit": row.amount_unit,
                "probability_status": "unresolved",
                "probability_method": "no_identity_evidence",
                "evidence_kind": "unresolved",
                "evidence_ids": "",
                "source": row.source,
                "quality_status": "unresolved_attribution",
            }
        )
    return pd.DataFrame(rows, columns=DISTRIBUTION_COLUMNS)
