from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stock_model.data import REQUIRED_COLUMNS, load_price_csv


MOTION_SCHEMA_VERSION = "stock_motion_event_v2"
MOTION_COLUMNS = [
    "schema_version",
    "event_id",
    "entity_id",
    "source_schema",
    "source_record_id",
    "source_entity_id",
    "dimension_id",
    "dimension_name",
    "event_time",
    "available_time",
    "availability_policy",
    "channel",
    "value",
    "unit",
    "evidence_kind",
    "method",
    "source",
    "market",
    "adjustment",
    "volume_unit",
    "quality_status",
]


CHANNEL_SPECS: dict[str, dict[str, str]] = {
    "market.price.open": {
        "column": "open",
        "unit": "source_currency_per_share",
        "evidence_kind": "observation",
        "method": "source_value",
    },
    "market.price.high": {
        "column": "high",
        "unit": "source_currency_per_share",
        "evidence_kind": "observation",
        "method": "source_value",
    },
    "market.price.low": {
        "column": "low",
        "unit": "source_currency_per_share",
        "evidence_kind": "observation",
        "method": "source_value",
    },
    "market.price.close": {
        "column": "close",
        "unit": "source_currency_per_share",
        "evidence_kind": "observation",
        "method": "source_value",
    },
    "market.activity.volume": {
        "column": "volume",
        "unit": "source_volume_unit",
        "evidence_kind": "observation",
        "method": "source_value",
    },
    "market.motion.return_1d": {
        "column": "return_1d",
        "unit": "ratio",
        "evidence_kind": "derived",
        "method": "close_t/close_t-1-1",
    },
    "market.motion.log_return_1d": {
        "column": "log_return_1d",
        "unit": "log_ratio",
        "evidence_kind": "derived",
        "method": "ln(close_t)-ln(close_t-1)",
    },
    "market.motion.gap_return": {
        "column": "gap_return",
        "unit": "ratio",
        "evidence_kind": "derived",
        "method": "open_t/close_t-1-1",
    },
    "market.motion.intraday_return": {
        "column": "intraday_return",
        "unit": "ratio",
        "evidence_kind": "derived",
        "method": "close_t/open_t-1",
    },
    "market.motion.range_ratio": {
        "column": "range_ratio",
        "unit": "ratio",
        "evidence_kind": "derived",
        "method": "(high_t-low_t)/close_(t-1)",
    },
    "market.state.close_location": {
        "column": "close_location",
        "unit": "ratio_0_1",
        "evidence_kind": "derived",
        "method": "(close_t-low_t)/(high_t-low_t)",
    },
    "market.activity.log_volume_change_1d": {
        "column": "log_volume_change_1d",
        "unit": "log_ratio",
        "evidence_kind": "derived",
        "method": "ln(1+volume_t)-ln(1+volume_t-1)",
    },
    "market.activity.volume_ratio_20": {
        "column": "volume_ratio_20",
        "unit": "ratio",
        "evidence_kind": "derived",
        "method": "volume_t/mean(volume_t-19:t)",
    },
    "market.risk.volatility_20": {
        "column": "volatility_20",
        "unit": "daily_return_std",
        "evidence_kind": "derived",
        "method": "std(return_1d,t-19:t)",
    },
    "market.relative.price_zscore_60": {
        "column": "price_zscore_60",
        "unit": "standard_deviation",
        "evidence_kind": "derived",
        "method": "zscore(ln(close),t-59:t)",
    },
    "proxy.directional_activity_pressure": {
        "column": "directional_activity_pressure",
        "unit": "proxy_index",
        "evidence_kind": "proxy",
        "method": "sign(return_1d)*ln(1+volume_ratio_20)",
    },
}


UNRESOLVED_LATENT_CHANNELS = [
    "production.capacity_state",
    "production.unit_economics_state",
    "claim.distributable_value_anchor",
    "expectation.revision_state",
    "sentiment.state",
    "capital.net_flow_state",
    "constraint.regime_state",
]


def build_market_motion_stream(
    prices: pd.DataFrame,
    *,
    symbol: str,
    source: str = "unknown",
    market: str = "unknown",
    adjustment: str = "unknown",
    volume_unit: str = "unknown",
) -> pd.DataFrame:
    """Convert canonical daily OHLCV into a causal, long-form motion stream.

    Every derived value uses only the current bar and earlier bars. The stream
    intentionally does not infer production, sentiment, expectations, or net
    capital flow from OHLCV alone.
    """
    frame = _normalize_prices(prices)
    state = _build_backward_looking_state(frame)
    provenance_key = f"{source}|{market}|{adjustment}|{volume_unit}"
    provenance_id = hashlib.sha256(provenance_key.encode("utf-8")).hexdigest()[:12]
    quality_status = (
        "limited_unknown_provenance"
        if any(value == "unknown" for value in [source, market, adjustment, volume_unit])
        else "usable_with_declared_provenance"
    )

    event_time = state["date"].dt.strftime("%Y-%m-%d")
    parts: list[pd.DataFrame] = []
    for channel, spec in CHANNEL_SPECS.items():
        values = state[spec["column"]]
        available = values.notna()
        if not available.any():
            continue
        part = pd.DataFrame(
            {
                "schema_version": MOTION_SCHEMA_VERSION,
                "entity_id": symbol,
                "source_schema": "ohlcv_daily_v1",
                "source_entity_id": symbol,
                "event_time": event_time[available],
                "available_time": event_time[available],
                "availability_policy": "available_after_session_close",
                "channel": channel,
                "value": values[available].astype(float),
                "unit": spec["unit"],
                "evidence_kind": spec["evidence_kind"],
                "method": spec["method"],
                "source": source,
                "market": market,
                "adjustment": adjustment,
                "volume_unit": volume_unit,
                "quality_status": quality_status,
            }
        )
        part["event_id"] = (
            part["entity_id"].astype(str)
            + "|"
            + part["event_time"].astype(str)
            + "|"
            + part["channel"].astype(str)
            + "|"
            + provenance_id
        )
        part["source_record_id"] = part["event_id"]
        part["dimension_id"] = pd.NA
        part["dimension_name"] = pd.NA
        parts.append(part)

    if not parts:
        return pd.DataFrame(columns=MOTION_COLUMNS)
    stream = pd.concat(parts, ignore_index=True)
    stream = stream[MOTION_COLUMNS].sort_values(
        ["event_time", "channel"], kind="stable"
    )
    return stream.reset_index(drop=True)


def build_network_motion_stream(
    tables: Any,
    *,
    symbol: str,
    market: str = "A-share",
) -> pd.DataFrame:
    """Map reviewed production evidence and anonymous concentrations to motion events."""
    from stock_model.industry_network import (
        ACTIVITY_PRODUCT_CANDIDATE_COLUMNS,
        BUSINESS_ACTIVITY_COLUMNS,
        COUNTERPARTY_CONCENTRATION_COLUMNS,
        PRODUCT_COLUMNS,
    )

    for frame, columns, name in [
        (tables.business_activities, BUSINESS_ACTIVITY_COLUMNS, "business activities"),
        (tables.products, PRODUCT_COLUMNS, "products"),
        (
            tables.activity_product_candidates,
            ACTIVITY_PRODUCT_CANDIDATE_COLUMNS,
            "activity product candidates",
        ),
        (
            tables.counterparty_concentrations,
            COUNTERPARTY_CONCENTRATION_COLUMNS,
            "counterparty concentrations",
        ),
    ]:
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            raise ValueError(f"{name} is missing columns: {missing}")

    listing = tables.listings[
        tables.listings["symbol"].astype(str).eq(symbol)
    ]
    if listing.empty:
        raise ValueError(f"Symbol not found in network: {symbol}")
    company_id = str(listing.iloc[0]["company_id"])
    activities = tables.business_activities.set_index("activity_id")
    products = tables.products.set_index("product_id")
    rows: list[dict[str, Any]] = []

    approved = tables.activity_product_candidates[
        tables.activity_product_candidates["company_id"].astype(str).eq(company_id)
        & tables.activity_product_candidates["review_status"].eq("approved")
    ]
    for mapping in approved.itertuples(index=False):
        activity = activities.loc[mapping.activity_id]
        product = products.loc[mapping.product_id]
        reviewed_at = pd.to_datetime(mapping.reviewed_at, utc=True, format="mixed")
        if pd.isna(reviewed_at):
            raise ValueError(f"Approved mapping lacks reviewed_at: {mapping.mapping_id}")
        event_time = str(activity["available_time"])
        channel = f"production.activity.product_role.{mapping.role}"
        rows.append(
            _network_motion_row(
                entity_id=symbol,
                source_schema="a_share_industry_network_v2",
                source_record_id=str(mapping.mapping_id),
                source_entity_id=company_id,
                dimension_id=str(mapping.product_id),
                dimension_name=str(product["canonical_name"]),
                event_time=event_time,
                available_time=reviewed_at.isoformat(),
                availability_policy="available_after_human_review",
                channel=channel,
                value=1.0,
                unit="binary_indicator",
                evidence_kind="observation",
                method="human_approved_verbatim_main_business_mapping",
                source=str(activity["source"]),
                market=market,
                quality_status="human_reviewed_source_evidence",
            )
        )

    concentrations = tables.counterparty_concentrations[
        tables.counterparty_concentrations["company_id"].astype(str).eq(company_id)
    ]
    for record in concentrations.itertuples(index=False):
        side = str(record.counterparty_side)
        names_disclosed = str(record.names_disclosed).strip().lower() in {
            "true",
            "1",
            "yes",
        }
        if names_disclosed:
            continue
        base = "customer" if side == "customer" else "supplier"
        event_time = str(record.report_period_end)
        for suffix, value in [
            ("top_five_share", record.share_of_total),
            ("related_party_share", record.related_party_share_of_total),
        ]:
            rows.append(
                _network_motion_row(
                    entity_id=symbol,
                    source_schema="a_share_industry_network_v2",
                    source_record_id=str(record.concentration_id),
                    source_entity_id=company_id,
                    dimension_id=f"ANONYMOUS_{base.upper()}_{record.scope.upper()}",
                    dimension_name=f"anonymous_{base}_{record.scope}",
                    event_time=event_time,
                    available_time=str(record.available_time),
                    availability_policy="available_after_source_ingestion",
                    channel=f"proxy.production.network.{base}.{suffix}",
                    value=float(value),
                    unit="ratio_of_annual_total",
                    evidence_kind="proxy",
                    method="anonymous_annual_report_concentration_as_network_dependency_proxy",
                    source=str(record.source),
                    market=market,
                    quality_status="verified_anonymous_aggregate_proxy",
                )
            )
    if not rows:
        return pd.DataFrame(columns=MOTION_COLUMNS)
    stream = pd.DataFrame(rows, columns=MOTION_COLUMNS)
    if stream["event_id"].duplicated().any():
        raise ValueError("Network motion event_id must be unique")
    return stream.sort_values(["event_time", "channel"], kind="stable").reset_index(
        drop=True
    )


def merge_motion_streams(*streams: pd.DataFrame) -> pd.DataFrame:
    """Merge internal streams without silently colliding event identities."""
    non_empty = [stream for stream in streams if not stream.empty]
    if not non_empty:
        return pd.DataFrame(columns=MOTION_COLUMNS)
    for stream in non_empty:
        _validate_motion_columns(stream)
    merged = pd.concat(non_empty, ignore_index=True)
    if merged["event_id"].duplicated().any():
        raise ValueError("Motion streams contain duplicate event_id values")
    return merged[MOTION_COLUMNS].sort_values(
        ["event_time", "channel", "entity_id"], kind="stable"
    ).reset_index(drop=True)


def motion_stream_as_of(
    stream: pd.DataFrame, *, as_of: str | pd.Timestamp
) -> pd.DataFrame:
    """Filter any v2 stream by its actual available time."""
    _validate_motion_columns(stream)
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    available = pd.to_datetime(
        stream["available_time"], errors="coerce", utc=True, format="mixed"
    )
    return stream[available.notna() & available.le(cutoff)].reset_index(drop=True)


def _network_motion_row(**kwargs: Any) -> dict[str, Any]:
    event_key = "|".join(
        str(kwargs[field])
        for field in ["entity_id", "event_time", "channel", "source_record_id"]
    )
    event_id = hashlib.sha256(event_key.encode("utf-8")).hexdigest()[:24]
    return {
        "schema_version": MOTION_SCHEMA_VERSION,
        "event_id": f"MOTION_{event_id}",
        **kwargs,
    }


def motion_stream_to_ohlcv(stream: pd.DataFrame) -> pd.DataFrame:
    """Recover the observed OHLCV view used by legacy feature code."""
    required = {
        "market.price.open": "open",
        "market.price.high": "high",
        "market.price.low": "low",
        "market.price.close": "close",
        "market.activity.volume": "volume",
    }
    _validate_motion_columns(stream)
    observed = stream[stream["channel"].isin(required)].copy()
    wide = observed.pivot(index="event_time", columns="channel", values="value")
    missing = [channel for channel in required if channel not in wide.columns]
    if missing:
        raise ValueError(f"Motion stream is missing observed channels: {missing}")
    result = wide[list(required)].rename(columns=required).reset_index()
    result = result.rename(columns={"event_time": "date"})
    result.columns.name = None
    result["date"] = pd.to_datetime(result["date"])
    return result[REQUIRED_COLUMNS].sort_values("date").reset_index(drop=True)


def build_motion_metadata(
    stream: pd.DataFrame,
    *,
    input_path: Path,
    output_path: Path,
    symbol: str,
    source: str,
    market: str,
    adjustment: str,
    volume_unit: str,
    source_metadata_path: Path | None,
    input_schema: str = "ohlcv_daily_v1",
    additional_input_files: list[str] | None = None,
) -> dict[str, Any]:
    _validate_motion_columns(stream)
    availability_policies = sorted(
        stream["availability_policy"].dropna().astype(str).unique().tolist()
    )
    channels = []
    for channel, group in stream.groupby("channel", sort=True):
        channels.append(
            {
                "channel": channel,
                "unit": str(group.iloc[0]["unit"]),
                "evidence_kind": str(group.iloc[0]["evidence_kind"]),
                "method": str(group.iloc[0]["method"]),
            }
        )
    return {
        "schema_version": MOTION_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_schema": input_schema,
        "input_file": str(input_path),
        "input_sha256": _sha256(input_path),
        "source_metadata_file": str(source_metadata_path) if source_metadata_path else None,
        "additional_input_files": additional_input_files or [],
        "output_file": str(output_path),
        "symbol": symbol,
        "source": source,
        "market": market,
        "adjustment": adjustment,
        "volume_unit": volume_unit,
        "provenance_id": hashlib.sha256(
            f"{source}|{market}|{adjustment}|{volume_unit}".encode("utf-8")
        ).hexdigest()[:12],
        "availability_policy": (
            availability_policies[0]
            if len(availability_policies) == 1
            else "multiple_policies"
        ),
        "availability_policies": availability_policies,
        "causality_policy": "current_and_past_rows_only",
        "rows": int(len(stream)),
        "event_dates": int(stream["event_time"].nunique()),
        "date_start": stream["event_time"].min() if not stream.empty else None,
        "date_end": stream["event_time"].max() if not stream.empty else None,
        "channels": channels,
        "unresolved_latent_channels": UNRESOLVED_LATENT_CHANNELS,
        "warnings": [
            "OHLCV cannot identify production value, expectations, sentiment, or net capital flow by itself.",
            "Proxy channels are hypotheses for testing, not direct observations of their possible causes.",
        ],
    }


def convert_ohlcv_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    symbol: str | None = None,
    source: str | None = None,
    market: str | None = None,
    adjustment: str | None = None,
    volume_unit: str | None = None,
    source_metadata_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    input_file = Path(input_path)
    output_file = Path(output_path)
    meta_file = _resolve_source_metadata(input_file, source_metadata_path)
    source_meta = _load_json(meta_file) if meta_file else {}

    resolved_symbol = symbol or source_meta.get("symbol") or input_file.stem
    resolved_source = source or source_meta.get("source") or "unknown"
    resolved_market = market or source_meta.get("market") or "unknown"
    resolved_adjustment = adjustment or source_meta.get("adjustment") or "unknown"
    resolved_volume_unit = volume_unit or source_meta.get("volume_unit") or "unknown"

    prices = load_price_csv(input_file)
    stream = build_market_motion_stream(
        prices,
        symbol=resolved_symbol,
        source=resolved_source,
        market=resolved_market,
        adjustment=resolved_adjustment,
        volume_unit=resolved_volume_unit,
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stream.to_csv(output_file, index=False)
    output_meta_path = Path(f"{output_file}.meta.json")
    metadata = build_motion_metadata(
        stream,
        input_path=input_file,
        output_path=output_file,
        symbol=resolved_symbol,
        source=resolved_source,
        market=resolved_market,
        adjustment=resolved_adjustment,
        volume_unit=resolved_volume_unit,
        source_metadata_path=meta_file,
    )
    output_meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return stream, metadata, output_meta_path


def _normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in prices.columns]
    if missing:
        raise ValueError(f"Prices are missing required columns: {missing}")
    frame = prices[REQUIRED_COLUMNS].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Price values must be positive.")
    if (frame["volume"] < 0).any():
        raise ValueError("Volume values must be non-negative.")
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    return frame.reset_index(drop=True)


def _build_backward_looking_state(frame: pd.DataFrame) -> pd.DataFrame:
    state = frame.copy()
    close = state["close"]
    previous_close = close.shift(1)
    state["return_1d"] = close.pct_change(fill_method=None)
    state["log_return_1d"] = np.log(close).diff()
    state["gap_return"] = state["open"] / previous_close - 1
    state["intraday_return"] = close / state["open"] - 1
    state["range_ratio"] = (state["high"] - state["low"]) / previous_close
    daily_range = state["high"] - state["low"]
    state["close_location"] = (close - state["low"]) / daily_range.replace(0, np.nan)

    log_volume = np.log1p(state["volume"])
    state["log_volume_change_1d"] = log_volume.diff()
    volume_mean_20 = state["volume"].rolling(20, min_periods=20).mean()
    state["volume_ratio_20"] = state["volume"] / volume_mean_20.replace(0, np.nan)
    state["volatility_20"] = state["return_1d"].rolling(20, min_periods=20).std()

    log_close = np.log(close)
    mean_60 = log_close.rolling(60, min_periods=60).mean()
    std_60 = log_close.rolling(60, min_periods=60).std()
    state["price_zscore_60"] = (log_close - mean_60) / std_60.replace(0, np.nan)
    state["directional_activity_pressure"] = (
        np.sign(state["return_1d"]) * np.log1p(state["volume_ratio_20"])
    )
    return state


def _validate_motion_columns(stream: pd.DataFrame) -> None:
    missing = [column for column in MOTION_COLUMNS if column not in stream.columns]
    if missing:
        raise ValueError(f"Motion stream is missing columns: {missing}")


def _resolve_source_metadata(
    input_file: Path, explicit_path: str | Path | None
) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"Source metadata not found: {path}")
        return path
    candidate = Path(f"{input_file}.meta.json")
    return candidate if candidate.exists() else None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert canonical daily OHLCV into the internal stock motion stream."
    )
    parser.add_argument("--input", required=True, help="Canonical OHLCV CSV path.")
    parser.add_argument("--output", required=True, help="Output motion stream CSV path.")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--source", default=None)
    parser.add_argument("--market", default=None)
    parser.add_argument("--adjustment", default=None)
    parser.add_argument("--volume-unit", default=None)
    parser.add_argument("--source-meta", default=None, help="Optional OHLCV .meta.json path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stream, metadata, meta_path = convert_ohlcv_file(
        args.input,
        args.output,
        symbol=args.symbol,
        source=args.source,
        market=args.market,
        adjustment=args.adjustment,
        volume_unit=args.volume_unit,
        source_metadata_path=args.source_meta,
    )
    print(f"Motion events: {len(stream)}")
    print(f"Event dates: {metadata['event_dates']}")
    print(f"Saved motion stream: {args.output}")
    print(f"Saved audit metadata: {meta_path}")


if __name__ == "__main__":
    main()
