from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


NETWORK_SCHEMA_VERSION = "a_share_industry_network_v2"
IMPACT_SCHEMA_VERSION = "a_share_listing_impact_v1"

COMPANY_COLUMNS = [
    "company_id",
    "company_name",
    "identity_basis",
    "issuer_id",
    "issuer_id_source",
    "registered_region",
    "source",
    "source_status",
    "observed_at",
]

LISTING_COLUMNS = [
    "listing_id",
    "company_id",
    "symbol",
    "exchange",
    "board",
    "security_type",
    "currency",
    "initial_status",
    "listing_date",
    "delisting_date",
    "total_market_value",
    "free_float_market_value",
    "source",
    "source_status",
    "observed_at",
]

INDUSTRY_COLUMNS = [
    "industry_id",
    "industry_code",
    "industry_name",
    "classification_system",
    "source",
    "source_status",
    "observed_at",
]

MEMBERSHIP_COLUMNS = [
    "membership_id",
    "company_id",
    "industry_id",
    "valid_from",
    "valid_to",
    "available_time",
    "source",
    "evidence_kind",
    "confidence",
]

RELATION_COLUMNS = [
    "relation_id",
    "source_company_id",
    "target_company_id",
    "relation_type",
    "product_or_service",
    "weight",
    "weight_unit",
    "valid_from",
    "valid_to",
    "available_time",
    "source",
    "evidence_kind",
    "confidence",
]

BUSINESS_ACTIVITY_COLUMNS = [
    "activity_id",
    "company_id",
    "activity_type",
    "activity_text",
    "product_or_service",
    "role",
    "valid_from",
    "valid_to",
    "available_time",
    "source",
    "source_record_id",
    "evidence_kind",
    "extraction_method",
    "confidence",
    "source_status",
]

PRODUCT_COLUMNS = [
    "product_id",
    "canonical_name",
    "parent_product_id",
    "product_kind",
    "description",
    "source",
    "source_status",
    "observed_at",
]

ACTIVITY_PRODUCT_CANDIDATE_COLUMNS = [
    "mapping_id",
    "activity_id",
    "company_id",
    "product_id",
    "role",
    "evidence_quote",
    "available_time",
    "mapping_method",
    "review_status",
    "reviewer",
    "reviewed_at",
    "confidence",
    "notes",
]

COUNTERPARTY_CONCENTRATION_COLUMNS = [
    "concentration_id",
    "company_id",
    "report_period_start",
    "report_period_end",
    "counterparty_side",
    "scope",
    "aggregate_amount",
    "currency",
    "share_of_total",
    "related_party_share_of_total",
    "names_disclosed",
    "announcement_time",
    "available_time",
    "source",
    "source_record_id",
    "evidence_pages",
    "evidence_quote",
    "extraction_method",
    "review_status",
    "confidence",
    "source_status",
]

COUNTERPARTY_RELATION_ELIGIBILITY_COLUMNS = [
    "audit_id",
    "concentration_id",
    "source_company_id",
    "counterparty_side",
    "names_disclosed",
    "available_time",
    "source",
    "source_record_id",
    "evidence_pages",
    "decision",
    "eligible_for_company_relation",
    "reason_code",
    "required_next_evidence",
    "relation_rows_created",
]

NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS = [
    "evidence_id",
    "relation_id",
    "reporting_company_id",
    "reporting_symbol",
    "reporting_legal_name",
    "counterparty_company_id",
    "counterparty_symbol",
    "counterparty_legal_name",
    "counterparty_name_in_filing",
    "report_period_start",
    "report_period_end",
    "transaction_direction",
    "relation_type",
    "product_or_service",
    "transaction_amount",
    "currency",
    "announcement_time",
    "source_available_time",
    "identity_announcement_time",
    "identity_available_time",
    "relation_available_time",
    "source",
    "source_record_id",
    "source_url",
    "evidence_page",
    "evidence_quote",
    "reporting_identity_evidence_page",
    "reporting_identity_evidence_quote",
    "identity_source",
    "identity_source_record_id",
    "identity_source_url",
    "identity_evidence_page",
    "identity_evidence_quote",
    "extraction_method",
    "review_status",
    "reviewed_at",
    "confidence",
    "source_status",
]

NAMED_COUNTERPARTY_RELATION_INPUT_COLUMNS = [
    column
    for column in NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS
    if column not in {"evidence_id", "relation_id"}
]

NAMED_RELATION_CORROBORATION_COLUMNS = [
    "corroboration_id",
    "evidence_id",
    "relation_id",
    "corroboration_kind",
    "source_company_id",
    "subject_company_id",
    "subject_symbol",
    "subject_legal_name",
    "reported_control_label",
    "reported_direct_ownership_share",
    "source",
    "source_record_id",
    "source_url",
    "source_announcement_time",
    "source_available_time",
    "evidence_pages",
    "evidence_quote",
    "reviewed_at",
    "available_time",
    "extraction_method",
    "review_status",
    "conclusion",
    "confidence",
    "source_status",
]

NAMED_RELATION_CORROBORATION_INPUT_COLUMNS = [
    column
    for column in NAMED_RELATION_CORROBORATION_COLUMNS
    if column not in {"corroboration_id", "relation_id"}
]

EVENT_COLUMNS = [
    "event_id",
    "listing_id",
    "company_id",
    "event_type",
    "event_time",
    "available_time",
    "effective_time",
    "industry_id",
    "fundraising_amount",
    "free_float_market_value",
    "reason",
    "source",
    "evidence_kind",
    "availability_quality",
    "source_status",
]

IMPACT_COLUMNS = [
    "schema_version",
    "impact_id",
    "source_event_id",
    "company_id",
    "listing_id",
    "industry_id",
    "event_time",
    "available_time",
    "effective_time",
    "impact_channel",
    "value",
    "unit",
    "evidence_kind",
    "method",
    "source",
    "availability_quality",
]

EVENT_TARGET_STATUS = {
    "listing_announced": "pre_listing",
    "listed": "active",
    "relisted": "active",
    "trading_suspended": "suspended",
    "trading_resumed": "active",
    "delisting_risk_warning": "delisting_risk",
    "delisting_announced": "delisting_announced",
    "delisted": "delisted",
    "status_observed_active": "observed_active_candidate",
    "status_observed_delisted": "observed_delisted_candidate",
}

VERIFIED_NETWORK_STATUSES = {
    "active",
    "suspended",
    "delisting_risk",
    "delisting_announced",
}
UNVERIFIED_NETWORK_STATUSES = {"observed_active_candidate"}


@dataclass
class NetworkTables:
    companies: pd.DataFrame
    listings: pd.DataFrame
    industries: pd.DataFrame
    memberships: pd.DataFrame
    relations: pd.DataFrame
    business_activities: pd.DataFrame
    lifecycle_events: pd.DataFrame
    products: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=PRODUCT_COLUMNS)
    )
    activity_product_candidates: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=ACTIVITY_PRODUCT_CANDIDATE_COLUMNS
        )
    )
    counterparty_concentrations: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=COUNTERPARTY_CONCENTRATION_COLUMNS
        )
    )


@dataclass
class NetworkSnapshot:
    companies: pd.DataFrame
    listings: pd.DataFrame
    industries: pd.DataFrame
    memberships: pd.DataFrame
    relations: pd.DataFrame
    business_activities: pd.DataFrame
    pending_events: pd.DataFrame
    market_impacts: pd.DataFrame
    products: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=PRODUCT_COLUMNS)
    )
    activity_product_candidates: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=ACTIVITY_PRODUCT_CANDIDATE_COLUMNS
        )
    )
    counterparty_concentrations: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            columns=COUNTERPARTY_CONCENTRATION_COLUMNS
        )
    )


def apply_lifecycle_events(
    listings: pd.DataFrame,
    events: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply only events known and effective by ``as_of``.

    Events that are already known but not effective are returned as pending.
    This separates expectation effects from structural network changes.
    """
    _require_columns(listings, LISTING_COLUMNS, "listings")
    _require_columns(events, EVENT_COLUMNS, "lifecycle_events")
    if listings["listing_id"].duplicated().any():
        raise ValueError("listing_id must be unique")

    cutoff = _as_utc(as_of)
    normalized_events = events.copy()
    for column in ["event_time", "available_time", "effective_time"]:
        normalized_events[column] = pd.to_datetime(
            normalized_events[column], errors="coerce", utc=True, format="mixed"
        )
    if normalized_events[["event_time", "available_time", "effective_time"]].isna().any().any():
        raise ValueError("Lifecycle event times must be valid and timezone-aware or UTC-normalizable")

    known = normalized_events[normalized_events["available_time"] <= cutoff].copy()
    effective = known[known["effective_time"] <= cutoff].sort_values(
        ["effective_time", "available_time", "event_id"], kind="stable"
    )
    pending = known[known["effective_time"] > cutoff].sort_values(
        ["effective_time", "available_time", "event_id"], kind="stable"
    )

    result = listings.copy()
    result["lifecycle_status"] = result["initial_status"].fillna("unknown")
    result["status_event_id"] = pd.NA
    result["status_effective_time"] = pd.Series(
        pd.NaT, index=result.index, dtype="datetime64[ns, UTC]"
    )
    index_by_listing = {value: index for index, value in result["listing_id"].items()}

    for _, event in effective.iterrows():
        listing_id = event["listing_id"]
        if listing_id not in index_by_listing:
            raise ValueError(f"Lifecycle event references unknown listing_id: {listing_id}")
        target = EVENT_TARGET_STATUS.get(event["event_type"])
        if target is None:
            continue
        row_index = index_by_listing[listing_id]
        current = result.at[row_index, "lifecycle_status"]
        if event["event_type"].startswith("status_observed_") and current != "unknown":
            continue
        if current == "delisted" and event["event_type"] not in {
            "relisted",
            "status_observed_delisted",
        }:
            raise ValueError(
                f"Invalid transition from delisted via {event['event_type']} for {listing_id}"
            )
        result.at[row_index, "lifecycle_status"] = target
        result.at[row_index, "status_event_id"] = event["event_id"]
        result.at[row_index, "status_effective_time"] = event["effective_time"]

    return result, pending.reset_index(drop=True)


def build_network_snapshot(
    tables: NetworkTables,
    *,
    as_of: str | pd.Timestamp,
    include_unverified: bool = False,
) -> NetworkSnapshot:
    _validate_tables(tables)
    listings, pending = apply_lifecycle_events(
        tables.listings, tables.lifecycle_events, as_of=as_of
    )
    included_statuses = set(VERIFIED_NETWORK_STATUSES)
    if include_unverified:
        included_statuses.update(UNVERIFIED_NETWORK_STATUSES)
    listings["network_included"] = listings["lifecycle_status"].isin(included_statuses)

    included_company_ids = set(
        listings.loc[listings["network_included"], "company_id"].astype(str)
    )
    companies = tables.companies.copy()
    companies["network_included"] = companies["company_id"].astype(str).isin(
        included_company_ids
    )

    memberships = _filter_temporal_edges(tables.memberships, as_of=as_of)
    memberships["network_active"] = memberships["company_id"].astype(str).isin(
        included_company_ids
    )
    active_industries = set(
        memberships.loc[memberships["network_active"], "industry_id"].astype(str)
    )
    industries = tables.industries.copy()
    industries["network_active"] = industries["industry_id"].astype(str).isin(
        active_industries
    )

    relations = _filter_temporal_edges(tables.relations, as_of=as_of)
    relations["network_active"] = (
        relations["source_company_id"].astype(str).isin(included_company_ids)
        & relations["target_company_id"].astype(str).isin(included_company_ids)
    )
    business_activities = _filter_temporal_edges(
        tables.business_activities, as_of=as_of
    )
    business_activities["network_active"] = business_activities[
        "company_id"
    ].astype(str).isin(included_company_ids)
    activity_product_candidates = _filter_available_rows(
        tables.activity_product_candidates, as_of=as_of
    )
    activity_product_candidates["network_active"] = (
        activity_product_candidates["company_id"]
        .astype(str)
        .isin(included_company_ids)
    )
    concentrations = _filter_available_rows(
        tables.counterparty_concentrations, as_of=as_of
    )
    concentrations["network_active"] = (
        concentrations["company_id"].astype(str).isin(included_company_ids)
    )
    referenced_product_ids = set(
        activity_product_candidates["product_id"].astype(str)
    )
    products = tables.products.copy()
    products["network_active"] = products["product_id"].astype(str).isin(
        referenced_product_ids
    )
    impacts = build_market_impact_stream(
        tables.lifecycle_events, listings=tables.listings, as_of=as_of
    )
    return NetworkSnapshot(
        companies=companies,
        listings=listings,
        industries=industries,
        memberships=memberships,
        relations=relations,
        business_activities=business_activities,
        pending_events=pending,
        market_impacts=impacts,
        products=products,
        activity_product_candidates=activity_product_candidates,
        counterparty_concentrations=concentrations,
    )


def build_market_impact_stream(
    events: pd.DataFrame,
    *,
    listings: pd.DataFrame,
    as_of: str | pd.Timestamp,
    include_unknown_historical_availability: bool = False,
) -> pd.DataFrame:
    """Build accounting impacts and explicit proxies from known lifecycle events."""
    _require_columns(events, EVENT_COLUMNS, "lifecycle_events")
    _require_columns(listings, LISTING_COLUMNS, "listings")
    cutoff = _as_utc(as_of)
    frame = events.copy()
    for column in ["event_time", "available_time", "effective_time"]:
        frame[column] = pd.to_datetime(
            frame[column], errors="coerce", utc=True, format="mixed"
        )
    frame = frame[frame["available_time"] <= cutoff].copy()
    if not include_unknown_historical_availability:
        frame = frame[
            frame["availability_quality"] != "historical_availability_unknown"
        ].copy()
    listing_industry = listings[["listing_id", "company_id"]].copy()
    frame = frame.merge(
        listing_industry,
        on=["listing_id", "company_id"],
        how="left",
        validate="many_to_one",
    )

    rows: list[dict[str, Any]] = []
    for _, event in frame.iterrows():
        event_type = event["event_type"]
        structural = event["effective_time"] <= cutoff
        count_change: tuple[str, float] | None = None
        if event_type == "listing_announced":
            count_change = ("market.structure.pending_listing_count_change", 1.0)
        elif event_type == "delisting_announced":
            count_change = ("market.structure.pending_delisting_count_change", 1.0)
        elif structural and event_type in {"listed", "relisted"}:
            count_change = ("market.structure.listed_security_count_change", 1.0)
        elif structural and event_type == "delisted":
            count_change = ("market.structure.listed_security_count_change", -1.0)
        if count_change:
            rows.append(
                _impact_row(
                    event,
                    channel=count_change[0],
                    value=count_change[1],
                    unit="security_count",
                    evidence_kind="structural_accounting",
                    method=f"event_type={event_type}",
                )
            )

        fundraising = _optional_float(event.get("fundraising_amount"))
        if structural and event_type in {"listed", "relisted"} and fundraising is not None:
            rows.append(
                _impact_row(
                    event,
                    channel="market.structure.primary_fundraising_amount",
                    value=fundraising,
                    unit="source_currency",
                    evidence_kind="reported_measure",
                    method="lifecycle_event.fundraising_amount",
                )
            )

        float_value = _optional_float(event.get("free_float_market_value"))
        if structural and float_value is not None and event_type in {"listed", "relisted", "delisted"}:
            direction = -1.0 if event_type == "delisted" else 1.0
            rows.append(
                _impact_row(
                    event,
                    channel="market.structure.free_float_value_entry_exit",
                    value=direction * float_value,
                    unit="source_currency",
                    evidence_kind="reported_measure",
                    method=f"signed_by_event_type={event_type}",
                )
            )
            if event_type == "delisted":
                rows.append(
                    _impact_row(
                        event,
                        channel="proxy.market.forced_reallocation_exposure",
                        value=abs(float_value),
                        unit="source_currency_exposure_proxy",
                        evidence_kind="proxy",
                        method="abs(pre_delisting_free_float_market_value)",
                    )
                )

    if not rows:
        return pd.DataFrame(columns=IMPACT_COLUMNS)
    return pd.DataFrame(rows)[IMPACT_COLUMNS].sort_values(
        ["available_time", "source_event_id", "impact_channel"], kind="stable"
    ).reset_index(drop=True)


def seed_from_spot_snapshot(spot: pd.DataFrame) -> NetworkTables:
    """Create an explicitly unverified network seed from a dated A-share snapshot."""
    required = [
        "fetched_at",
        "symbol",
        "name",
        "total_market_value",
        "free_float_market_value",
    ]
    _require_columns(spot, required, "spot snapshot")
    frame = spot.copy()
    if frame["symbol"].duplicated().any():
        raise ValueError("Spot snapshot contains duplicate symbols")
    observed_at = pd.to_datetime(frame["fetched_at"], errors="raise")
    if observed_at.dt.tz is None:
        observed_at = observed_at.dt.tz_localize("Asia/Shanghai")
    observed_iso = observed_at.map(lambda value: value.isoformat())

    frame["company_id"] = frame["symbol"].map(_temporary_company_id)
    frame["listing_id"] = frame["symbol"].map(lambda value: f"LISTING_{value}_UNKNOWN_SPELL")
    companies = pd.DataFrame(
        {
            "company_id": frame["company_id"],
            "company_name": frame["name"].fillna("unknown"),
            "identity_basis": "temporary_symbol_proxy",
            "issuer_id": pd.NA,
            "issuer_id_source": "unknown",
            "registered_region": "unknown",
            "source": "AkShare A-share spot snapshot",
            "source_status": "stale_unverified_snapshot_seed",
            "observed_at": observed_iso,
        }
    )
    listings = pd.DataFrame(
        {
            "listing_id": frame["listing_id"],
            "company_id": frame["company_id"],
            "symbol": frame["symbol"],
            "exchange": frame["symbol"].map(_exchange_from_symbol),
            "board": frame["symbol"].map(_board_from_symbol),
            "security_type": "A_share_common_equity_candidate",
            "currency": "CNY",
            "initial_status": "unknown",
            "listing_date": pd.NA,
            "delisting_date": pd.NA,
            "total_market_value": pd.to_numeric(
                frame["total_market_value"], errors="coerce"
            ),
            "free_float_market_value": pd.to_numeric(
                frame["free_float_market_value"], errors="coerce"
            ),
            "source": "AkShare A-share spot snapshot",
            "source_status": "stale_unverified_snapshot_seed",
            "observed_at": observed_iso,
        }
    )

    delisted_marker = frame["name"].astype(str).str.contains("退市", na=False)
    events = pd.DataFrame(
        {
            "event_id": [
                _stable_id("SNAPSHOT_STATUS", symbol, timestamp)
                for symbol, timestamp in zip(frame["symbol"], observed_iso)
            ],
            "listing_id": frame["listing_id"],
            "company_id": frame["company_id"],
            "event_type": delisted_marker.map(
                {True: "status_observed_delisted", False: "status_observed_active"}
            ),
            "event_time": observed_iso,
            "available_time": observed_iso,
            "effective_time": observed_iso,
            "industry_id": pd.NA,
            "fundraising_amount": pd.NA,
            "free_float_market_value": listings["free_float_market_value"],
            "reason": delisted_marker.map(
                {True: "security name contains 退市; not official lifecycle proof", False: "present in spot snapshot"}
            ),
            "source": "AkShare A-share spot snapshot",
            "evidence_kind": delisted_marker.map(
                {True: "proxy", False: "observation"}
            ),
            "availability_quality": "observed_at_fetch_time",
            "source_status": "stale_unverified_snapshot_seed",
        }
    )
    return NetworkTables(
        companies=companies[COMPANY_COLUMNS],
        listings=listings[LISTING_COLUMNS],
        industries=pd.DataFrame(columns=INDUSTRY_COLUMNS),
        memberships=pd.DataFrame(columns=MEMBERSHIP_COLUMNS),
        relations=pd.DataFrame(columns=RELATION_COLUMNS),
        business_activities=pd.DataFrame(columns=BUSINESS_ACTIVITY_COLUMNS),
        lifecycle_events=events[EVENT_COLUMNS],
    )


def tables_from_baostock(
    basic: pd.DataFrame,
    industry: pd.DataFrame,
    *,
    fetched_at: str,
) -> NetworkTables:
    """Map free BaoStock tables into the internal network contract."""
    _require_columns(
        basic, ["code", "code_name", "ipoDate", "outDate", "type", "status"], "BaoStock basic"
    )
    _require_columns(
        industry,
        ["updateDate", "code", "code_name", "industry", "industryClassification"],
        "BaoStock industry",
    )
    stocks = basic[basic["type"].astype(str) == "1"].copy()
    stocks["symbol"] = stocks["code"].map(_baostock_code_to_symbol)
    stocks = stocks[stocks["symbol"].notna()].drop_duplicates("symbol", keep="last")
    stocks["company_id"] = stocks["symbol"].map(_temporary_company_id)
    stocks["listing_id"] = stocks["symbol"].map(
        lambda value: f"LISTING_{value}_UNKNOWN_SPELL"
    )

    companies = pd.DataFrame(
        {
            "company_id": stocks["company_id"],
            "company_name": stocks["code_name"].replace("", "unknown"),
            "identity_basis": "temporary_symbol_proxy",
            "issuer_id": pd.NA,
            "issuer_id_source": "unknown",
            "registered_region": "unknown",
            "source": "BaoStock query_stock_basic",
            "source_status": "imported_unverified",
            "observed_at": fetched_at,
        }
    )
    listings = pd.DataFrame(
        {
            "listing_id": stocks["listing_id"],
            "company_id": stocks["company_id"],
            "symbol": stocks["symbol"],
            "exchange": stocks["symbol"].map(_exchange_from_symbol),
            "board": stocks["symbol"].map(_board_from_symbol),
            "security_type": "A_share_common_equity",
            "currency": "CNY",
            "initial_status": "unknown",
            "listing_date": stocks["ipoDate"].replace("", pd.NA),
            "delisting_date": stocks["outDate"].replace("", pd.NA),
            "total_market_value": pd.NA,
            "free_float_market_value": pd.NA,
            "source": "BaoStock query_stock_basic",
            "source_status": "imported_unverified",
            "observed_at": fetched_at,
        }
    )

    industry_rows = industry.copy()
    industry_rows["symbol"] = industry_rows["code"].map(_baostock_code_to_symbol)
    industry_rows = industry_rows[industry_rows["symbol"].isin(set(stocks["symbol"]))]
    industry_rows = industry_rows[industry_rows["industry"].fillna("").str.strip() != ""].copy()
    industry_rows["industry_code"] = industry_rows["industry"].str.extract(
        r"^([A-Z]\d{2})", expand=False
    ).fillna("unknown")
    industry_rows["industry_name"] = industry_rows.apply(
        lambda row: row["industry"][len(row["industry_code"]):]
        if row["industry_code"] != "unknown"
        else row["industry"],
        axis=1,
    )
    industry_rows["industry_id"] = industry_rows.apply(
        lambda row: _stable_id(
            "INDUSTRY", row["industryClassification"], row["industry"]
        ),
        axis=1,
    )
    industries = (
        industry_rows[
            ["industry_id", "industry_code", "industry_name", "industryClassification"]
        ]
        .drop_duplicates("industry_id")
        .rename(columns={"industryClassification": "classification_system"})
    )
    industries["source"] = "BaoStock query_stock_industry"
    industries["source_status"] = "imported_unverified"
    industries["observed_at"] = fetched_at

    symbol_to_company = dict(zip(stocks["symbol"], stocks["company_id"]))
    memberships = pd.DataFrame(
        {
            "membership_id": industry_rows.apply(
                lambda row: _stable_id(
                    "MEMBERSHIP", symbol_to_company[row["symbol"]], row["industry_id"]
                ),
                axis=1,
            ),
            "company_id": industry_rows["symbol"].map(symbol_to_company),
            "industry_id": industry_rows["industry_id"],
            "valid_from": industry_rows["updateDate"].replace("", pd.NA),
            "valid_to": pd.NA,
            "available_time": fetched_at,
            "source": "BaoStock query_stock_industry",
            "evidence_kind": "observation",
            "confidence": "medium",
        }
    )

    event_rows: list[dict[str, Any]] = []
    for _, row in stocks.iterrows():
        common = {
            "listing_id": row["listing_id"],
            "company_id": row["company_id"],
            "available_time": fetched_at,
            "industry_id": pd.NA,
            "fundraising_amount": pd.NA,
            "free_float_market_value": pd.NA,
            "source": "BaoStock query_stock_basic",
            "evidence_kind": "observation",
            "availability_quality": "historical_availability_unknown",
            "source_status": "imported_unverified",
        }
        if row["ipoDate"]:
            event_rows.append(
                {
                    **common,
                    "event_id": _stable_id("LISTED", row["listing_id"], row["ipoDate"]),
                    "event_type": "listed",
                    "event_time": row["ipoDate"],
                    "effective_time": row["ipoDate"],
                    "reason": "BaoStock ipoDate; historical availability not supplied",
                }
            )
        if row["outDate"]:
            event_rows.append(
                {
                    **common,
                    "event_id": _stable_id("DELISTED", row["listing_id"], row["outDate"]),
                    "event_type": "delisted",
                    "event_time": row["outDate"],
                    "effective_time": row["outDate"],
                    "reason": "BaoStock outDate; historical availability not supplied",
                }
            )
        observed_type = (
            "status_observed_active" if str(row["status"]) == "1" else "status_observed_delisted"
        )
        event_rows.append(
            {
                **common,
                "event_id": _stable_id("STATUS", row["listing_id"], fetched_at),
                "event_type": observed_type,
                "event_time": fetched_at,
                "effective_time": fetched_at,
                "reason": f"BaoStock raw status={row['status']}; 1 mapped active, other mapped delisted candidate",
                "availability_quality": "observed_at_fetch_time",
            }
        )
    events = pd.DataFrame(event_rows, columns=EVENT_COLUMNS)
    return NetworkTables(
        companies=companies[COMPANY_COLUMNS].reset_index(drop=True),
        listings=listings[LISTING_COLUMNS].reset_index(drop=True),
        industries=industries[INDUSTRY_COLUMNS].reset_index(drop=True),
        memberships=memberships[MEMBERSHIP_COLUMNS].reset_index(drop=True),
        relations=pd.DataFrame(columns=RELATION_COLUMNS),
        business_activities=pd.DataFrame(columns=BUSINESS_ACTIVITY_COLUMNS),
        lifecycle_events=events[EVENT_COLUMNS].reset_index(drop=True),
    )


def add_missing_snapshot_candidates(
    primary: NetworkTables, candidates: NetworkTables
) -> tuple[NetworkTables, int]:
    """Add symbols absent from a primary source without upgrading their evidence status."""
    _validate_tables(primary)
    _validate_tables(candidates)
    existing_symbols = set(primary.listings["symbol"].astype(str))
    new_listings = candidates.listings[
        ~candidates.listings["symbol"].astype(str).isin(existing_symbols)
    ].copy()
    new_company_ids = set(new_listings["company_id"].astype(str))
    new_companies = candidates.companies[
        candidates.companies["company_id"].astype(str).isin(new_company_ids)
    ].copy()
    new_events = candidates.lifecycle_events[
        candidates.lifecycle_events["listing_id"].astype(str).isin(
            set(new_listings["listing_id"].astype(str))
        )
    ].copy()
    combined = NetworkTables(
        companies=pd.concat([primary.companies, new_companies], ignore_index=True),
        listings=pd.concat([primary.listings, new_listings], ignore_index=True),
        industries=primary.industries.copy(),
        memberships=primary.memberships.copy(),
        relations=primary.relations.copy(),
        business_activities=primary.business_activities.copy(),
        lifecycle_events=pd.concat(
            [primary.lifecycle_events, new_events], ignore_index=True
        ),
        products=primary.products.copy(),
        activity_product_candidates=primary.activity_product_candidates.copy(),
        counterparty_concentrations=primary.counterparty_concentrations.copy(),
    )
    _validate_tables(combined)
    return combined, len(new_listings)


def merge_incremental_network_refresh(
    previous: NetworkTables,
    current: NetworkTables,
    *,
    previous_refresh_time: str,
    current_refresh_time: str,
) -> NetworkTables:
    """Preserve lifecycle history and mark genuinely new lifecycle facts safely.

    A newly observed listing/delisting is usable no earlier than the current
    refresh. If its effective date predates the previous refresh date, it stays
    classified as a historical correction with unknown original availability.
    """
    _validate_tables(previous)
    _validate_tables(current)
    previous_cutoff = _as_utc(previous_refresh_time)
    current_events = current.lifecycle_events.copy()
    existing_event_ids = set(previous.lifecycle_events["event_id"].astype(str))
    is_new = ~current_events["event_id"].astype(str).isin(existing_event_ids)
    structural = current_events["event_type"].isin({"listed", "relisted", "delisted"})
    effective = pd.to_datetime(
        current_events["effective_time"], errors="coerce", utc=True, format="mixed"
    )
    first_observed = is_new & structural & (
        effective.dt.date >= previous_cutoff.date()
    )
    current_events.loc[first_observed, "availability_quality"] = (
        "first_observed_after_previous_refresh"
    )
    current_events.loc[first_observed, "available_time"] = current_refresh_time

    new_events = current_events[is_new]
    combined_events = pd.concat(
        [previous.lifecycle_events, new_events], ignore_index=True
    ).drop_duplicates("event_id", keep="first")

    combined = NetworkTables(
        # Preserve richer identity/profile fields already collected; current adds new issuers.
        companies=_upsert(current.companies, previous.companies, "company_id"),
        listings=_upsert(previous.listings, current.listings, "listing_id"),
        industries=_upsert(previous.industries, current.industries, "industry_id"),
        memberships=_upsert(
            previous.memberships, current.memberships, "membership_id"
        ),
        relations=_upsert(previous.relations, current.relations, "relation_id"),
        business_activities=_upsert(
            previous.business_activities,
            current.business_activities,
            "activity_id",
        ),
        lifecycle_events=combined_events[EVENT_COLUMNS].reset_index(drop=True),
        products=_upsert(previous.products, current.products, "product_id"),
        activity_product_candidates=_upsert(
            previous.activity_product_candidates,
            current.activity_product_candidates,
            "mapping_id",
        ),
        counterparty_concentrations=_upsert(
            previous.counterparty_concentrations,
            current.counterparty_concentrations,
            "concentration_id",
        ),
    )
    _validate_tables(combined)
    return combined


def apply_cninfo_issuer_identity(
    tables: NetworkTables,
    registry: pd.DataFrame,
    *,
    available_time: str,
) -> tuple[NetworkTables, pd.DataFrame]:
    """Replace symbol-proxy company IDs with CNINFO issuer orgIds where available."""
    _validate_tables(tables)
    _require_columns(
        registry, ["code", "orgId", "zwjc", "category"], "CNINFO issuer registry"
    )
    issuers = registry[registry["category"].astype(str) == "A股"].copy()
    issuers["code"] = issuers["code"].astype(str).str.zfill(6)
    issuers = issuers.drop_duplicates("code", keep="last")
    issuer_by_code = issuers.set_index("code")

    listing_map = tables.listings[["listing_id", "company_id", "symbol"]].copy()
    listing_map["security_code"] = listing_map["symbol"].astype(str).str.split(".").str[0]
    listing_map["cninfo_org_id"] = listing_map["security_code"].map(
        issuer_by_code["orgId"]
    )
    listing_map["cninfo_name"] = listing_map["security_code"].map(
        issuer_by_code["zwjc"]
    )
    listing_map["old_company_id"] = listing_map["company_id"]
    listing_map["new_company_id"] = listing_map.apply(
        lambda row: (
            f"CNINFO_ORG_{row['cninfo_org_id']}"
            if pd.notna(row["cninfo_org_id"]) and str(row["cninfo_org_id"]).strip()
            else row["old_company_id"]
        ),
        axis=1,
    )
    listing_map["match_method"] = listing_map["cninfo_org_id"].notna().map(
        {True: "security_code_to_cninfo_org_id", False: "unmapped_keep_existing_id"}
    )
    listing_map["available_time"] = available_time
    listing_map["source"] = "CNINFO szse_stock.json"
    listing_map["source_status"] = "imported_unverified"

    old_to_new = dict(
        zip(listing_map["old_company_id"], listing_map["new_company_id"])
    )
    old_to_issuer = dict(
        zip(listing_map["old_company_id"], listing_map["cninfo_org_id"])
    )
    companies = tables.companies.copy()
    companies["company_id"] = companies["company_id"].map(
        lambda value: old_to_new.get(value, value)
    )
    companies["issuer_id"] = companies["issuer_id"].where(
        companies["issuer_id"].notna(),
        companies.index.to_series().map(
            lambda index: old_to_issuer.get(tables.companies.at[index, "company_id"])
        ),
    )
    mapped = companies["issuer_id"].notna()
    companies.loc[mapped, "identity_basis"] = "cninfo_org_id"
    companies.loc[mapped, "issuer_id_source"] = "CNINFO orgId"
    companies.loc[mapped, "source"] = "CNINFO stock registry + prior company source"
    companies.loc[mapped, "source_status"] = "identity_mapped_imported_unverified"
    companies.loc[mapped, "observed_at"] = available_time
    companies = companies.drop_duplicates("company_id", keep="last")

    listings = tables.listings.copy()
    listings["company_id"] = listings["company_id"].map(
        lambda value: old_to_new.get(value, value)
    )
    memberships = tables.memberships.copy()
    memberships["company_id"] = memberships["company_id"].map(
        lambda value: old_to_new.get(value, value)
    )
    if not memberships.empty:
        memberships["membership_id"] = memberships.apply(
            lambda row: _stable_id(
                "MEMBERSHIP", row["company_id"], row["industry_id"]
            ),
            axis=1,
        )
        memberships = memberships.drop_duplicates("membership_id", keep="last")

    relations = tables.relations.copy()
    if not relations.empty:
        for column in ["source_company_id", "target_company_id"]:
            relations[column] = relations[column].map(
                lambda value: old_to_new.get(value, value)
            )
        relations["relation_id"] = relations.apply(
            lambda row: _stable_id(
                "RELATION",
                row["source_company_id"],
                row["target_company_id"],
                row["relation_type"],
                row["product_or_service"],
                row["valid_from"],
                row["valid_to"],
                row["weight"],
                row["weight_unit"],
            ),
            axis=1,
        )
        relations = relations.drop_duplicates("relation_id", keep="last")

    activities = tables.business_activities.copy()
    old_to_new_activity: dict[str, str] = {}
    if not activities.empty:
        activities["old_activity_id"] = activities["activity_id"]
        activities["company_id"] = activities["company_id"].map(
            lambda value: old_to_new.get(value, value)
        )
        activities["activity_id"] = activities.apply(
            lambda row: _stable_id(
                "ACTIVITY", row["company_id"], row["activity_type"], row["activity_text"]
            ),
            axis=1,
        )
        old_to_new_activity = dict(
            zip(activities["old_activity_id"], activities["activity_id"])
        )
        activities = activities.drop(columns="old_activity_id")
        activities = activities.drop_duplicates("activity_id", keep="first")

    product_candidates = tables.activity_product_candidates.copy()
    if not product_candidates.empty:
        product_candidates["company_id"] = product_candidates["company_id"].map(
            lambda value: old_to_new.get(value, value)
        )
        product_candidates["activity_id"] = product_candidates["activity_id"].map(
            lambda value: old_to_new_activity.get(value, value)
        )
        product_candidates["mapping_id"] = product_candidates.apply(
            lambda row: _stable_id(
                "ACTIVITY_PRODUCT",
                row["activity_id"],
                row["product_id"],
                row["role"],
            ),
            axis=1,
        )
        product_candidates = product_candidates.drop_duplicates(
            "mapping_id", keep="first"
        )

    concentrations = tables.counterparty_concentrations.copy()
    if not concentrations.empty:
        concentrations["company_id"] = concentrations["company_id"].map(
            lambda value: old_to_new.get(value, value)
        )
        concentrations["concentration_id"] = concentrations.apply(
            lambda row: _stable_id(
                "COUNTERPARTY_CONCENTRATION",
                row["company_id"],
                row["report_period_end"],
                row["counterparty_side"],
                row["scope"],
            ),
            axis=1,
        )
        concentrations = concentrations.drop_duplicates(
            "concentration_id", keep="first"
        )

    events = tables.lifecycle_events.copy()
    events["company_id"] = events["company_id"].map(
        lambda value: old_to_new.get(value, value)
    )
    mapped_tables = NetworkTables(
        companies=companies[COMPANY_COLUMNS].reset_index(drop=True),
        listings=listings[LISTING_COLUMNS].reset_index(drop=True),
        industries=tables.industries.copy(),
        memberships=memberships[MEMBERSHIP_COLUMNS].reset_index(drop=True),
        relations=relations[RELATION_COLUMNS].reset_index(drop=True),
        business_activities=activities[BUSINESS_ACTIVITY_COLUMNS].reset_index(drop=True),
        lifecycle_events=events[EVENT_COLUMNS].reset_index(drop=True),
        products=tables.products.copy(),
        activity_product_candidates=product_candidates[
            ACTIVITY_PRODUCT_CANDIDATE_COLUMNS
        ].reset_index(drop=True),
        counterparty_concentrations=concentrations[
            COUNTERPARTY_CONCENTRATION_COLUMNS
        ].reset_index(drop=True),
    )
    _validate_tables(mapped_tables)
    audit_columns = [
        "listing_id",
        "symbol",
        "old_company_id",
        "new_company_id",
        "cninfo_org_id",
        "cninfo_name",
        "match_method",
        "available_time",
        "source",
        "source_status",
    ]
    return mapped_tables, listing_map[audit_columns].reset_index(drop=True)


def business_activities_from_cninfo_profile(
    profile: pd.DataFrame,
    *,
    company_id: str,
    issuer_id: str,
    security_code: str,
    available_time: str,
) -> pd.DataFrame:
    """Convert verbatim CNINFO profile fields into internal business evidence."""
    if profile.empty:
        return pd.DataFrame(columns=BUSINESS_ACTIVITY_COLUMNS)
    _require_columns(profile, ["主营业务", "经营范围"], "CNINFO company profile")
    row = profile.iloc[0]
    records: list[dict[str, Any]] = []
    for activity_type, field in [
        ("main_business_description", "主营业务"),
        ("business_scope_description", "经营范围"),
    ]:
        text = row.get(field)
        if pd.isna(text) or not str(text).strip():
            continue
        text = str(text).strip()
        records.append(
            {
                "activity_id": _stable_id(
                    "ACTIVITY", company_id, activity_type, text
                ),
                "company_id": company_id,
                "activity_type": activity_type,
                "activity_text": text,
                "product_or_service": "unparsed",
                "role": "unknown",
                "valid_from": pd.NA,
                "valid_to": pd.NA,
                "available_time": available_time,
                "source": "CNINFO p_sysapi1133 company profile",
                "source_record_id": f"{issuer_id}|{security_code}|{field}",
                "evidence_kind": "verbatim_observation",
                "extraction_method": "verbatim_profile_field",
                "confidence": "medium",
                "source_status": "imported_unverified",
            }
        )
    return pd.DataFrame(records, columns=BUSINESS_ACTIVITY_COLUMNS)


def product_mapping_candidates_from_activity(
    activity: pd.Series,
    *,
    canonical_name: str,
    roles: list[str],
    available_time: str,
    evidence_quote: str,
    notes: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a vocabulary node and reviewable mappings without asserting a fact."""
    _require_columns(
        pd.DataFrame([activity]),
        BUSINESS_ACTIVITY_COLUMNS,
        "business activity",
    )
    canonical_name = canonical_name.strip()
    evidence_quote = evidence_quote.strip()
    if not canonical_name:
        raise ValueError("canonical_name cannot be empty")
    if not roles or any(not str(role).strip() for role in roles):
        raise ValueError("At least one non-empty role is required")
    if evidence_quote not in str(activity["activity_text"]):
        raise ValueError("evidence_quote must occur verbatim in activity_text")
    product_id = _stable_id("PRODUCT", canonical_name)
    product = pd.DataFrame(
        [
            {
                "product_id": product_id,
                "canonical_name": canonical_name,
                "parent_product_id": pd.NA,
                "product_kind": "physical_good",
                "description": "Controlled vocabulary node; does not by itself assert company activity.",
                "source": "manual ontology seed from verbatim business evidence",
                "source_status": "manually_defined_vocabulary",
                "observed_at": available_time,
            }
        ],
        columns=PRODUCT_COLUMNS,
    )
    mappings = []
    for role in roles:
        normalized_role = str(role).strip()
        mappings.append(
            {
                "mapping_id": _stable_id(
                    "ACTIVITY_PRODUCT",
                    activity["activity_id"],
                    product_id,
                    normalized_role,
                ),
                "activity_id": activity["activity_id"],
                "company_id": activity["company_id"],
                "product_id": product_id,
                "role": normalized_role,
                "evidence_quote": evidence_quote,
                "available_time": available_time,
                "mapping_method": "manual_rule_from_exact_main_business_quote",
                "review_status": "pending_human_review",
                "reviewer": pd.NA,
                "reviewed_at": pd.NA,
                "confidence": "high_text_match_unreviewed_claim",
                "notes": notes,
            }
        )
    return product, pd.DataFrame(
        mappings, columns=ACTIVITY_PRODUCT_CANDIDATE_COLUMNS
    )


def review_activity_product_candidates(
    candidates: pd.DataFrame,
    activities: pd.DataFrame,
    *,
    mapping_ids: list[str],
    decision: str,
    reviewer: str,
    reviewed_at: str,
    review_note: str = "",
) -> pd.DataFrame:
    """Record an explicit review decision while preserving the original candidate."""
    _require_columns(
        candidates,
        ACTIVITY_PRODUCT_CANDIDATE_COLUMNS,
        "activity product candidates",
    )
    _require_columns(activities, BUSINESS_ACTIVITY_COLUMNS, "business activities")
    if candidates["mapping_id"].duplicated().any():
        raise ValueError("mapping_id must be unique before review")
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer cannot be empty")
    reviewed_timestamp = _as_utc(reviewed_at).isoformat()
    selected_ids = {str(value) for value in mapping_ids}
    if not selected_ids:
        raise ValueError("At least one mapping_id is required")
    missing_ids = selected_ids - set(candidates["mapping_id"].astype(str))
    if missing_ids:
        raise ValueError(f"Unknown mapping_id values: {sorted(missing_ids)}")

    result = candidates.copy()
    for column in [
        "review_status",
        "reviewer",
        "reviewed_at",
        "confidence",
        "notes",
    ]:
        result[column] = result[column].astype("object")
    activity_text = activities.set_index("activity_id")["activity_text"].astype(str)
    for index, row in result[
        result["mapping_id"].astype(str).isin(selected_ids)
    ].iterrows():
        activity_id = str(row["activity_id"])
        if activity_id not in activity_text.index:
            raise ValueError(f"Candidate references unknown activity: {activity_id}")
        if str(row["evidence_quote"]) not in activity_text.loc[activity_id]:
            raise ValueError(
                f"Candidate evidence_quote is not verbatim for activity: {activity_id}"
            )
        existing_status = str(row["review_status"])
        if existing_status == decision:
            continue
        if existing_status not in {"pending_human_review", ""}:
            raise ValueError(
                f"Mapping {row['mapping_id']} already has review_status={existing_status}"
            )
        result.at[index, "review_status"] = decision
        result.at[index, "reviewer"] = reviewer
        result.at[index, "reviewed_at"] = reviewed_timestamp
        result.at[index, "confidence"] = (
            "human_reviewed_exact_text_match"
            if decision == "approved"
            else "human_reviewed_rejected"
        )
        if review_note.strip():
            prior_note = str(row["notes"]).strip()
            result.at[index, "notes"] = " ".join(
                value for value in [prior_note, review_note.strip()] if value
            )
    return result[ACTIVITY_PRODUCT_CANDIDATE_COLUMNS].reset_index(drop=True)


def counterparty_concentrations_from_annual_report(
    records: list[dict[str, Any]],
    *,
    company_id: str,
    report_period_start: str,
    report_period_end: str,
    announcement_time: str,
    available_time: str,
    source: str,
    source_record_id: str,
) -> pd.DataFrame:
    """Convert verified aggregate disclosure into non-edge exposure evidence."""
    rows: list[dict[str, Any]] = []
    for record in records:
        side = str(record["counterparty_side"]).strip()
        if side not in {"customer", "supplier"}:
            raise ValueError(f"Unsupported counterparty_side: {side}")
        share = float(record["share_of_total"])
        related_share = float(record["related_party_share_of_total"])
        if not (0 <= share <= 1 and 0 <= related_share <= 1):
            raise ValueError("Shares must be represented as decimal fractions between 0 and 1")
        names_disclosed = bool(record.get("names_disclosed", False))
        rows.append(
            {
                "concentration_id": _stable_id(
                    "COUNTERPARTY_CONCENTRATION",
                    company_id,
                    report_period_end,
                    side,
                    record.get("scope", "top_five"),
                ),
                "company_id": company_id,
                "report_period_start": report_period_start,
                "report_period_end": report_period_end,
                "counterparty_side": side,
                "scope": record.get("scope", "top_five"),
                "aggregate_amount": float(record["aggregate_amount"]),
                "currency": record.get("currency", "CNY"),
                "share_of_total": share,
                "related_party_share_of_total": related_share,
                "names_disclosed": names_disclosed,
                "announcement_time": announcement_time,
                "available_time": available_time,
                "source": source,
                "source_record_id": source_record_id,
                "evidence_pages": str(record["evidence_pages"]),
                "evidence_quote": str(record["evidence_quote"]).strip(),
                "extraction_method": record.get(
                    "extraction_method", "pypdf_text_plus_visual_verification"
                ),
                "review_status": record.get("review_status", "visually_verified"),
                "confidence": record.get("confidence", "high"),
                "source_status": record.get("source_status", "official_filing_archived"),
            }
        )
    return pd.DataFrame(rows, columns=COUNTERPARTY_CONCENTRATION_COLUMNS)


def audit_counterparty_relation_eligibility(
    concentrations: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
) -> pd.DataFrame:
    """Audit whether aggregate disclosures can create identified company edges.

    The concentration table does not store a resolved counterparty identity.
    A row that says names were disclosed therefore still needs separate
    verbatim-name and independent-identity evidence before relation creation.
    """
    required = [
        "concentration_id",
        "company_id",
        "counterparty_side",
        "names_disclosed",
        "available_time",
        "source",
        "source_record_id",
        "evidence_pages",
    ]
    _require_columns(concentrations, required, "counterparty_concentrations")
    cutoff = _as_utc(as_of)
    frame = concentrations.copy()
    frame["available_time"] = pd.to_datetime(
        frame["available_time"], errors="raise", utc=True, format="mixed"
    )
    frame = frame[frame["available_time"] <= cutoff].copy()
    rows: list[dict[str, Any]] = []
    for _, record in frame.iterrows():
        names_disclosed = _strict_boolean(record["names_disclosed"])
        if names_disclosed:
            decision = "insufficient_identity_evidence"
            reason_code = "aggregate_table_has_no_resolved_counterparty_identity"
        else:
            decision = "rejected"
            reason_code = "anonymous_aggregate_only"
        concentration_id = str(record["concentration_id"])
        rows.append(
            {
                "audit_id": _stable_id(
                    "COUNTERPARTY_RELATION_AUDIT",
                    concentration_id,
                    cutoff.isoformat(),
                ),
                "concentration_id": concentration_id,
                "source_company_id": str(record["company_id"]),
                "counterparty_side": str(record["counterparty_side"]),
                "names_disclosed": names_disclosed,
                "available_time": record["available_time"].isoformat(),
                "source": str(record["source"]),
                "source_record_id": str(record["source_record_id"]),
                "evidence_pages": str(record["evidence_pages"]),
                "decision": decision,
                "eligible_for_company_relation": False,
                "reason_code": reason_code,
                "required_next_evidence": (
                    "verbatim_legal_name+independent_company_identity+"
                    "reviewed_available_time"
                ),
                "relation_rows_created": 0,
            }
        )
    return pd.DataFrame(rows, columns=COUNTERPARTY_RELATION_ELIGIBILITY_COLUMNS)


def company_relations_from_named_counterparty_evidence(
    records: list[dict[str, Any]] | pd.DataFrame,
    *,
    companies: pd.DataFrame,
    as_of: str | pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate reviewed named-counterparty evidence and build period-bounded edges."""
    _require_columns(companies, ["company_id"], "companies")
    frame = pd.DataFrame(records).copy()
    _require_columns(
        frame,
        NAMED_COUNTERPARTY_RELATION_INPUT_COLUMNS,
        "named_counterparty_relation_evidence",
    )
    known_company_ids = set(companies["company_id"].astype(str))
    cutoff = _as_utc(as_of)
    evidence_rows: list[dict[str, Any]] = []
    relation_rows: list[dict[str, Any]] = []

    for _, record in frame.iterrows():
        reporting_company_id = str(record["reporting_company_id"]).strip()
        counterparty_company_id = str(record["counterparty_company_id"]).strip()
        if reporting_company_id not in known_company_ids:
            raise ValueError(f"Unknown reporting company: {reporting_company_id}")
        if counterparty_company_id not in known_company_ids:
            raise ValueError(f"Unknown counterparty company: {counterparty_company_id}")
        if reporting_company_id == counterparty_company_id:
            raise ValueError("A named counterparty relation must connect two companies")

        direction = str(record["transaction_direction"]).strip()
        if direction not in {"purchase_from", "sale_to"}:
            raise ValueError(f"Unsupported transaction_direction: {direction}")
        relation_type = str(record["relation_type"]).strip()
        if relation_type != "supplies":
            raise ValueError("Current named-counterparty importer only accepts supplies edges")

        report_start = pd.Timestamp(record["report_period_start"])
        report_end = pd.Timestamp(record["report_period_end"])
        if report_start > report_end:
            raise ValueError("report_period_start must not be after report_period_end")
        valid_to = report_end + pd.Timedelta(days=1)
        amount = float(record["transaction_amount"])
        if amount <= 0:
            raise ValueError("transaction_amount must be positive")

        counterparty_name = str(record["counterparty_name_in_filing"]).strip()
        counterparty_legal_name = str(record["counterparty_legal_name"]).strip()
        reporting_legal_name = str(record["reporting_legal_name"]).strip()
        evidence_quote = str(record["evidence_quote"]).strip()
        identity_quote = str(record["identity_evidence_quote"]).strip()
        reporting_identity_quote = str(
            record["reporting_identity_evidence_quote"]
        ).strip()
        if counterparty_name not in evidence_quote:
            raise ValueError("Transaction quote does not contain the disclosed counterparty name")
        if f"{amount:,.2f}" not in evidence_quote:
            raise ValueError("Transaction quote does not contain the disclosed amount")
        if counterparty_legal_name not in identity_quote:
            raise ValueError("Independent identity quote does not contain the legal name")
        if str(record["counterparty_symbol"]).split(".")[0] not in identity_quote:
            raise ValueError("Independent identity quote does not contain the security code")
        if reporting_legal_name not in reporting_identity_quote:
            raise ValueError("Reporting-company identity quote does not contain the legal name")

        announcement_time = _as_utc(record["announcement_time"])
        source_available_time = _as_utc(record["source_available_time"])
        identity_announcement_time = _as_utc(record["identity_announcement_time"])
        identity_available_time = _as_utc(record["identity_available_time"])
        reviewed_at = _as_utc(record["reviewed_at"])
        relation_available_time = _as_utc(record["relation_available_time"])
        if source_available_time < announcement_time:
            raise ValueError("Source availability cannot precede the official announcement")
        if identity_available_time < identity_announcement_time:
            raise ValueError("Identity availability cannot precede its official announcement")
        required_available_time = max(
            source_available_time, identity_available_time, reviewed_at
        )
        if relation_available_time < required_available_time:
            raise ValueError(
                "Relation availability must not precede source, identity, or review availability"
            )
        if str(record["review_status"]) != "visually_verified_and_identity_confirmed":
            raise ValueError("Named relation requires completed visual and identity review")

        if direction == "purchase_from":
            source_company_id = counterparty_company_id
            target_company_id = reporting_company_id
        else:
            source_company_id = reporting_company_id
            target_company_id = counterparty_company_id
        product_or_service = str(record["product_or_service"]).strip()
        evidence_id = _stable_id(
            "NAMED_COUNTERPARTY_EVIDENCE",
            reporting_company_id,
            counterparty_company_id,
            record["source_record_id"],
            direction,
            product_or_service,
            f"{amount:.2f}",
        )
        relation_id = _stable_id(
            "RELATION",
            source_company_id,
            target_company_id,
            relation_type,
            product_or_service,
            report_start.date().isoformat(),
            valid_to.date().isoformat(),
            f"{amount:.2f}",
            record["currency"],
        )
        evidence_row = record.to_dict()
        evidence_row.update(
            {
                "evidence_id": evidence_id,
                "relation_id": relation_id,
                "report_period_start": report_start.date().isoformat(),
                "report_period_end": report_end.date().isoformat(),
                "transaction_amount": amount,
                "announcement_time": announcement_time.isoformat(),
                "source_available_time": source_available_time.isoformat(),
                "identity_announcement_time": identity_announcement_time.isoformat(),
                "identity_available_time": identity_available_time.isoformat(),
                "relation_available_time": relation_available_time.isoformat(),
                "reviewed_at": reviewed_at.isoformat(),
            }
        )
        evidence_rows.append(evidence_row)
        if relation_available_time <= cutoff:
            relation_rows.append(
                {
                    "relation_id": relation_id,
                    "source_company_id": source_company_id,
                    "target_company_id": target_company_id,
                    "relation_type": relation_type,
                    "product_or_service": product_or_service,
                    "weight": amount,
                    "weight_unit": str(record["currency"]),
                    "valid_from": report_start.date().isoformat(),
                    "valid_to": valid_to.date().isoformat(),
                    "available_time": relation_available_time.isoformat(),
                    "source": str(record["source"]),
                    "evidence_kind": "annual_report_named_related_party_transaction",
                    "confidence": str(record["confidence"]),
                }
            )

    evidence = pd.DataFrame(
        evidence_rows, columns=NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS
    )
    if evidence["evidence_id"].duplicated().any():
        raise ValueError("evidence_id must be unique")
    relations = pd.DataFrame(relation_rows, columns=RELATION_COLUMNS)
    if relations["relation_id"].duplicated().any():
        raise ValueError("relation_id must be unique")
    return evidence, relations


def named_relation_corroborations_from_records(
    records: list[dict[str, Any]] | pd.DataFrame,
    *,
    named_evidence: pd.DataFrame,
    as_of: str | pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate counterparty-filing corroboration without upgrading transaction facts."""
    _require_columns(
        named_evidence,
        [
            "evidence_id",
            "relation_id",
            "reporting_company_id",
            "reporting_symbol",
            "reporting_legal_name",
            "counterparty_company_id",
        ],
        "named_counterparty_relation_evidence",
    )
    frame = pd.DataFrame(records).copy()
    _require_columns(
        frame,
        NAMED_RELATION_CORROBORATION_INPUT_COLUMNS,
        "named_relation_corroborations",
    )
    evidence_by_id = named_evidence.set_index("evidence_id", drop=False)
    cutoff = _as_utc(as_of)
    rows: list[dict[str, Any]] = []

    for _, record in frame.iterrows():
        evidence_id = str(record["evidence_id"])
        if evidence_id not in evidence_by_id.index:
            raise ValueError(f"Unknown named relation evidence: {evidence_id}")
        linked = evidence_by_id.loc[evidence_id]
        if isinstance(linked, pd.DataFrame):
            raise ValueError(f"Duplicate named relation evidence: {evidence_id}")
        if str(record["source_company_id"]) != str(linked["counterparty_company_id"]):
            raise ValueError("Corroboration source company does not match the counterparty")
        if str(record["subject_company_id"]) != str(linked["reporting_company_id"]):
            raise ValueError("Corroboration subject company does not match the reporter")
        if str(record["subject_symbol"]) != str(linked["reporting_symbol"]):
            raise ValueError("Corroboration subject symbol does not match the reporter")
        if str(record["subject_legal_name"]) != str(linked["reporting_legal_name"]):
            raise ValueError("Corroboration subject legal name does not match the reporter")

        corroboration_kind = str(record["corroboration_kind"])
        if corroboration_kind != "issuer_report_identity_and_control_link":
            raise ValueError(f"Unsupported corroboration kind: {corroboration_kind}")
        conclusion = str(record["conclusion"])
        expected_conclusion = (
            "corroborates_identity_and_control_link_not_transaction_amount_or_direction"
        )
        if conclusion != expected_conclusion:
            raise ValueError("Corroboration conclusion must preserve the transaction limit")
        quote = str(record["evidence_quote"]).strip()
        legal_name = str(record["subject_legal_name"])
        security_code = str(record["subject_symbol"]).split(".")[0]
        control_label = str(record["reported_control_label"])
        ownership_share = float(record["reported_direct_ownership_share"])
        if legal_name not in quote or security_code not in quote:
            raise ValueError("Corroboration quote must contain the subject legal name and code")
        if control_label not in quote:
            raise ValueError("Corroboration quote must contain the reported control label")
        if not 0 < ownership_share <= 1:
            raise ValueError("reported_direct_ownership_share must be a decimal fraction")
        if f"{ownership_share:.2%}" not in quote:
            raise ValueError("Corroboration quote must contain the reported ownership share")

        source_announcement_time = _as_utc(record["source_announcement_time"])
        source_available_time = _as_utc(record["source_available_time"])
        reviewed_at = _as_utc(record["reviewed_at"])
        available_time = _as_utc(record["available_time"])
        if source_available_time < source_announcement_time:
            raise ValueError("Corroboration availability cannot precede the announcement")
        if available_time < max(source_available_time, reviewed_at):
            raise ValueError("Corroboration availability cannot precede source or review")
        if str(record["review_status"]) != "visually_verified":
            raise ValueError("Corroboration requires completed visual review")

        row = record.to_dict()
        row.update(
            {
                "corroboration_id": _stable_id(
                    "NAMED_RELATION_CORROBORATION",
                    evidence_id,
                    record["source_record_id"],
                    corroboration_kind,
                ),
                "relation_id": str(linked["relation_id"]),
                "reported_direct_ownership_share": ownership_share,
                "source_announcement_time": source_announcement_time.isoformat(),
                "source_available_time": source_available_time.isoformat(),
                "reviewed_at": reviewed_at.isoformat(),
                "available_time": available_time.isoformat(),
            }
        )
        rows.append(row)

    normalized = pd.DataFrame(rows, columns=NAMED_RELATION_CORROBORATION_COLUMNS)
    if normalized["corroboration_id"].duplicated().any():
        raise ValueError("corroboration_id must be unique")
    available = normalized[
        pd.to_datetime(
            normalized["available_time"], errors="raise", utc=True, format="mixed"
        )
        <= cutoff
    ].reset_index(drop=True)
    return normalized, available


def write_network_tables(
    tables: NetworkTables,
    output_dir: str | Path,
    *,
    source_description: str,
) -> Path:
    _validate_tables(tables)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    table_map = {
        "companies.csv": tables.companies,
        "listings.csv": tables.listings,
        "industries.csv": tables.industries,
        "industry_memberships.csv": tables.memberships,
        "company_relations.csv": tables.relations,
        "business_activities.csv": tables.business_activities,
        "products.csv": tables.products,
        "activity_product_candidates.csv": tables.activity_product_candidates,
        "counterparty_concentrations.csv": tables.counterparty_concentrations,
        "lifecycle_events.csv": tables.lifecycle_events,
    }
    manifest_tables: dict[str, Any] = {}
    for name, frame in table_map.items():
        path = destination / name
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        manifest_tables[name] = {
            "rows": int(len(frame)),
            "sha256": _sha256(path),
            "columns": list(frame.columns),
        }
    named_evidence_path = destination / "named_counterparty_relation_evidence.csv"
    if named_evidence_path.exists():
        named_evidence = pd.read_csv(named_evidence_path)
        _require_columns(
            named_evidence,
            NAMED_COUNTERPARTY_RELATION_EVIDENCE_COLUMNS,
            "named_counterparty_relation_evidence",
        )
        manifest_tables[named_evidence_path.name] = {
            "rows": int(len(named_evidence)),
            "sha256": _sha256(named_evidence_path),
            "columns": list(named_evidence.columns),
        }
    corroboration_path = destination / "named_relation_corroborations.csv"
    if corroboration_path.exists():
        corroborations = pd.read_csv(corroboration_path)
        _require_columns(
            corroborations,
            NAMED_RELATION_CORROBORATION_COLUMNS,
            "named_relation_corroborations",
        )
        manifest_tables[corroboration_path.name] = {
            "rows": int(len(corroborations)),
            "sha256": _sha256(corroboration_path),
            "columns": list(corroborations.columns),
        }
    manifest = {
        "schema_version": NETWORK_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_description": source_description,
        "tables": manifest_tables,
        "known_limits": [
            (
                f"{int((tables.companies['identity_basis'] != 'cninfo_org_id').sum())} companies "
                "still lack a CNINFO orgId and retain a temporary identity"
            ),
            "industry membership is classification evidence, not a supplier-customer relation",
            (
                "company relation rows are period-bounded observations and must not be "
                "automatically continued beyond valid_to"
                if len(tables.relations)
                else "company_relations.csv stays empty until relation-specific evidence is imported"
            ),
            "pending activity-product mappings are candidates, not verified production facts",
            "anonymous counterparties create concentration records but no company relation edges",
            "historical listing dates fetched today retain today's available_time and must not be backfilled into old model states",
        ],
    }
    manifest_path = destination / "network.meta.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest_path


def load_network_tables(directory: str | Path) -> NetworkTables:
    source = Path(directory)
    companies = pd.read_csv(source / "companies.csv")
    if "issuer_id" not in companies.columns:
        companies["issuer_id"] = pd.NA
    if "issuer_id_source" not in companies.columns:
        companies["issuer_id_source"] = "unknown"
    activity_path = source / "business_activities.csv"
    business_activities = (
        pd.read_csv(activity_path)
        if activity_path.exists()
        else pd.DataFrame(columns=BUSINESS_ACTIVITY_COLUMNS)
    )
    product_path = source / "products.csv"
    candidate_path = source / "activity_product_candidates.csv"
    concentration_path = source / "counterparty_concentrations.csv"
    return NetworkTables(
        companies=companies[COMPANY_COLUMNS],
        listings=pd.read_csv(source / "listings.csv"),
        industries=pd.read_csv(source / "industries.csv"),
        memberships=pd.read_csv(source / "industry_memberships.csv"),
        relations=pd.read_csv(source / "company_relations.csv"),
        business_activities=business_activities,
        lifecycle_events=pd.read_csv(source / "lifecycle_events.csv"),
        products=(
            pd.read_csv(product_path)
            if product_path.exists()
            else pd.DataFrame(columns=PRODUCT_COLUMNS)
        ),
        activity_product_candidates=(
            pd.read_csv(candidate_path)
            if candidate_path.exists()
            else pd.DataFrame(columns=ACTIVITY_PRODUCT_CANDIDATE_COLUMNS)
        ),
        counterparty_concentrations=(
            pd.read_csv(concentration_path)
            if concentration_path.exists()
            else pd.DataFrame(columns=COUNTERPARTY_CONCENTRATION_COLUMNS)
        ),
    )


def write_network_snapshot(snapshot: NetworkSnapshot, output_dir: str | Path) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "companies_snapshot.csv": snapshot.companies,
        "listings_snapshot.csv": snapshot.listings,
        "industries_snapshot.csv": snapshot.industries,
        "industry_memberships_snapshot.csv": snapshot.memberships,
        "company_relations_snapshot.csv": snapshot.relations,
        "business_activities_snapshot.csv": snapshot.business_activities,
        "products_snapshot.csv": snapshot.products,
        "activity_product_candidates_snapshot.csv": snapshot.activity_product_candidates,
        "counterparty_concentrations_snapshot.csv": snapshot.counterparty_concentrations,
        "pending_lifecycle_events.csv": snapshot.pending_events,
        "listing_market_impacts.csv": snapshot.market_impacts,
    }.items():
        frame.to_csv(destination / name, index=False, encoding="utf-8-sig")


def _validate_tables(tables: NetworkTables) -> None:
    for frame, columns, name in [
        (tables.companies, COMPANY_COLUMNS, "companies"),
        (tables.listings, LISTING_COLUMNS, "listings"),
        (tables.industries, INDUSTRY_COLUMNS, "industries"),
        (tables.memberships, MEMBERSHIP_COLUMNS, "memberships"),
        (tables.relations, RELATION_COLUMNS, "relations"),
        (
            tables.business_activities,
            BUSINESS_ACTIVITY_COLUMNS,
            "business_activities",
        ),
        (tables.products, PRODUCT_COLUMNS, "products"),
        (
            tables.activity_product_candidates,
            ACTIVITY_PRODUCT_CANDIDATE_COLUMNS,
            "activity_product_candidates",
        ),
        (
            tables.counterparty_concentrations,
            COUNTERPARTY_CONCENTRATION_COLUMNS,
            "counterparty_concentrations",
        ),
        (tables.lifecycle_events, EVENT_COLUMNS, "lifecycle_events"),
    ]:
        _require_columns(frame, columns, name)
    if tables.companies["company_id"].duplicated().any():
        raise ValueError("company_id must be unique")
    if tables.listings["listing_id"].duplicated().any():
        raise ValueError("listing_id must be unique")
    company_ids = set(tables.companies["company_id"].astype(str))
    if not set(tables.listings["company_id"].astype(str)).issubset(company_ids):
        raise ValueError("Every listing must reference a known company")
    if not tables.relations.empty:
        relations = tables.relations
        if relations["relation_id"].duplicated().any():
            raise ValueError("relation_id must be unique")
        relation_company_ids = set(relations["source_company_id"].astype(str)) | set(
            relations["target_company_id"].astype(str)
        )
        if not relation_company_ids.issubset(company_ids):
            raise ValueError("Every relation must reference known companies")
    if not tables.products.empty and tables.products["product_id"].duplicated().any():
        raise ValueError("product_id must be unique")
    if not tables.activity_product_candidates.empty:
        candidates = tables.activity_product_candidates
        if candidates["mapping_id"].duplicated().any():
            raise ValueError("mapping_id must be unique")
        if not set(candidates["company_id"].astype(str)).issubset(company_ids):
            raise ValueError("Every product mapping candidate must reference a known company")
        product_ids = set(tables.products["product_id"].astype(str))
        if not set(candidates["product_id"].astype(str)).issubset(product_ids):
            raise ValueError("Every product mapping candidate must reference a known product")
        activity_ids = set(tables.business_activities["activity_id"].astype(str))
        if not set(candidates["activity_id"].astype(str)).issubset(activity_ids):
            raise ValueError("Every product mapping candidate must reference a known activity")
    if not tables.counterparty_concentrations.empty:
        concentrations = tables.counterparty_concentrations
        if concentrations["concentration_id"].duplicated().any():
            raise ValueError("concentration_id must be unique")
        if not set(concentrations["company_id"].astype(str)).issubset(company_ids):
            raise ValueError("Every concentration record must reference a known company")


def _filter_temporal_edges(frame: pd.DataFrame, *, as_of: str | pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        result = frame.copy()
        return result
    cutoff = _as_utc(as_of)
    result = frame.copy()
    available = pd.to_datetime(
        result["available_time"], errors="coerce", utc=True, format="mixed"
    )
    valid_from = pd.to_datetime(
        result["valid_from"], errors="coerce", utc=True, format="mixed"
    )
    valid_to = pd.to_datetime(
        result["valid_to"], errors="coerce", utc=True, format="mixed"
    )
    mask = (available <= cutoff) & (valid_from.isna() | (valid_from <= cutoff))
    mask &= valid_to.isna() | (valid_to > cutoff)
    return result[mask].reset_index(drop=True)


def _filter_available_rows(
    frame: pd.DataFrame, *, as_of: str | pd.Timestamp
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    cutoff = _as_utc(as_of)
    available = pd.to_datetime(
        frame["available_time"], errors="coerce", utc=True, format="mixed"
    )
    return frame[available.notna() & available.le(cutoff)].copy().reset_index(drop=True)


def _impact_row(
    event: pd.Series,
    *,
    channel: str,
    value: float,
    unit: str,
    evidence_kind: str,
    method: str,
) -> dict[str, Any]:
    return {
        "schema_version": IMPACT_SCHEMA_VERSION,
        "impact_id": _stable_id("IMPACT", event["event_id"], channel),
        "source_event_id": event["event_id"],
        "company_id": event["company_id"],
        "listing_id": event["listing_id"],
        "industry_id": event.get("industry_id", pd.NA),
        "event_time": event["event_time"],
        "available_time": event["available_time"],
        "effective_time": event["effective_time"],
        "impact_channel": channel,
        "value": value,
        "unit": unit,
        "evidence_kind": evidence_kind,
        "method": method,
        "source": event["source"],
        "availability_quality": event["availability_quality"],
    }


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value) or value == "":
        return None
    return float(value)


def _strict_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"Expected a strict boolean value, received: {value!r}")


def _require_columns(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")


def _as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _temporary_company_id(symbol: str) -> str:
    return f"CN_COMPANY_TEMP_{str(symbol).replace('.', '_')}"


def _exchange_from_symbol(symbol: str) -> str:
    suffix = str(symbol).split(".")[-1].upper()
    return {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}.get(suffix, "unknown")


def _board_from_symbol(symbol: str) -> str:
    code, _, suffix = str(symbol).partition(".")
    if suffix.upper() == "BJ":
        return "Beijing Stock Exchange"
    if suffix.upper() == "SH" and code.startswith("688"):
        return "STAR Market"
    if suffix.upper() == "SZ" and code.startswith(("300", "301")):
        return "ChiNext"
    if suffix.upper() in {"SH", "SZ"}:
        return "Main Board or other; requires source verification"
    return "unknown"


def _baostock_code_to_symbol(value: str) -> str | None:
    market, separator, code = str(value).partition(".")
    if not separator or market not in {"sh", "sz", "bj"}:
        return None
    return f"{code}.{market.upper()}"


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _upsert(previous: pd.DataFrame, current: pd.DataFrame, key: str) -> pd.DataFrame:
    if previous.empty:
        return current.copy().reset_index(drop=True)
    if current.empty:
        return previous.copy().reset_index(drop=True)
    return (
        pd.concat([previous, current], ignore_index=True)
        .drop_duplicates(key, keep="last")
        .reset_index(drop=True)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
