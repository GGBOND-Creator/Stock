from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

from stock_model.a_share import to_baostock_symbol, to_project_symbol


MINUTE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume", "amount"]
SUPPORTED_MINUTES = {5, 15, 30, 60}
MARKET_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class MinuteArchiveResult:
    output_path: Path
    metadata_path: Path
    fetched_rows: int
    previous_rows: int
    output_rows: int
    duplicate_timestamps_replaced: int
    trading_days: int


def fetch_baostock_minutes(
    symbol: str,
    *,
    start: str,
    end: str,
    frequency_minutes: int = 5,
    adjustflag: str = "3",
) -> pd.DataFrame:
    """Fetch A-share minute bars from BaoStock and normalize them.

    BaoStock supports 5/15/30/60-minute bars. The returned timestamps are bar
    end times in the Asia/Shanghai market session.
    """
    if frequency_minutes not in SUPPORTED_MINUTES:
        raise ValueError(f"BaoStock minute frequency must be one of {sorted(SUPPORTED_MINUTES)}.")
    if adjustflag not in {"1", "2", "3"}:
        raise ValueError("BaoStock adjustflag must be '1', '2', or '3'.")

    try:
        import baostock as bs
    except ImportError as exc:
        raise RuntimeError("Install baostock first: pip install baostock") from exc

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")

    try:
        query = bs.query_history_k_data_plus(
            to_baostock_symbol(symbol),
            "date,time,code,open,high,low,close,volume,amount,adjustflag",
            start_date=start,
            end_date=end,
            frequency=str(frequency_minutes),
            adjustflag=adjustflag,
        )
        if query.error_code != "0":
            raise RuntimeError(f"BaoStock minute query failed: {query.error_code} {query.error_msg}")

        rows = []
        while query.next():
            rows.append(query.get_row_data())
        frame = pd.DataFrame(rows, columns=query.fields)
    finally:
        bs.logout()

    if frame.empty:
        raise ValueError(f"BaoStock returned no {frequency_minutes}-minute data for {symbol} from {start} to {end}.")
    return normalize_baostock_minutes(frame)


def normalize_baostock_minutes(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["date", "time", "open", "high", "low", "close", "volume", "amount"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"BaoStock minute data is missing columns: {missing}")

    normalized = pd.DataFrame(index=frame.index)
    normalized["datetime"] = _parse_baostock_datetime(frame["date"], frame["time"])
    for column in MINUTE_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(frame[column], errors="coerce")

    if normalized[MINUTE_COLUMNS].isna().any(axis=None):
        invalid_rows = normalized.index[normalized[MINUTE_COLUMNS].isna().any(axis=1)].tolist()[:5]
        raise ValueError(f"BaoStock minute data contains missing or unparseable values at rows: {invalid_rows}")

    _validate_market_relationships(normalized)
    return normalized.sort_values("datetime").drop_duplicates("datetime", keep="last").reset_index(drop=True)


def load_minute_archive(path: str | Path) -> pd.DataFrame:
    archive_path = Path(path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"Minute archive not found: {archive_path}")
    frame = pd.read_csv(archive_path)
    missing = [column for column in MINUTE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Minute archive is missing columns: {missing}")
    normalized = frame[MINUTE_COLUMNS].copy()
    normalized["datetime"] = _coerce_market_datetime(normalized["datetime"])
    for column in MINUTE_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if normalized.isna().any(axis=None):
        raise ValueError(f"Minute archive contains missing or unparseable values: {archive_path}")
    _validate_market_relationships(normalized)
    if normalized["datetime"].duplicated().any():
        raise ValueError(f"Minute archive contains duplicate timestamps: {archive_path}")
    return normalized.sort_values("datetime").reset_index(drop=True)


def update_minute_archive(
    fetched: pd.DataFrame,
    output_path: str | Path,
    *,
    symbol: str,
    source: str,
    frequency_minutes: int,
    adjustment: str,
    volume_unit: str,
    amount_unit: str,
    requested_start: str,
    requested_end: str,
    timezone_name: str = "Asia/Shanghai",
) -> MinuteArchiveResult:
    if frequency_minutes not in SUPPORTED_MINUTES:
        raise ValueError(f"Minute frequency must be one of {sorted(SUPPORTED_MINUTES)}.")
    if list(fetched.columns) != MINUTE_COLUMNS:
        raise ValueError(f"Fetched minute columns must be exactly {MINUTE_COLUMNS}.")
    if fetched.empty:
        raise ValueError("Fetched minute data is empty.")

    new_rows = fetched.copy()
    new_rows["datetime"] = _coerce_market_datetime(new_rows["datetime"])
    if new_rows.isna().any(axis=None):
        raise ValueError("Fetched minute data contains missing or unparseable values.")
    _validate_market_relationships(new_rows)

    target_path = Path(output_path)
    metadata_path = target_path.with_suffix(target_path.suffix + ".meta.json")
    previous_metadata = {}
    if target_path.is_file() and not metadata_path.is_file():
        raise ValueError(f"Existing minute archive has no audit metadata: {metadata_path}")
    if metadata_path.is_file():
        previous_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_contract = {
            "source": source,
            "symbol": to_project_symbol(symbol),
            "frequency": f"{frequency_minutes}m",
            "timezone": timezone_name,
            "adjustment": adjustment,
            "volume_unit": volume_unit,
            "amount_unit": amount_unit,
        }
        mismatches = {
            key: {"archive": previous_metadata.get(key), "requested": value}
            for key, value in expected_contract.items()
            if previous_metadata.get(key) != value
        }
        if mismatches:
            raise ValueError(
                "Minute archive contract does not match this update; use a separate output path or perform an "
                f"explicit migration: {mismatches}"
            )
    previous = load_minute_archive(target_path) if target_path.is_file() else pd.DataFrame(columns=MINUTE_COLUMNS)
    combined = pd.concat([previous, new_rows], ignore_index=True)
    combined["datetime"] = _coerce_market_datetime(combined["datetime"])
    duplicate_timestamps = int(combined.duplicated("datetime", keep="last").sum())
    combined = combined.sort_values("datetime").drop_duplicates("datetime", keep="last").reset_index(drop=True)
    _validate_market_relationships(combined)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    output = combined[MINUTE_COLUMNS].copy()
    output["datetime"] = output["datetime"].map(lambda value: value.isoformat())
    temporary_output = target_path.with_suffix(target_path.suffix + ".tmp")
    output.to_csv(temporary_output, index=False, encoding="utf-8")
    temporary_output.replace(target_path)

    counts_by_day = combined.groupby(combined["datetime"].dt.date).size()
    expected_rows = 240 // frequency_minutes
    incomplete_days = {str(day): int(count) for day, count in counts_by_day.items() if count != expected_rows}
    warnings = []
    if incomplete_days:
        warnings.append(
            f"Found {len(incomplete_days)} trading dates with row counts other than the expected {expected_rows}; "
            "review suspensions, partial sessions, or source gaps."
        )

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous_initial_start = previous_metadata.get("initial_requested_start")
    initial_requested_start = min(
        [value for value in [previous_initial_start, requested_start] if value is not None]
    )
    metadata = {
        "schema_version": "ohlcv_minute_v1",
        "archive_created_at_utc": previous_metadata.get("archive_created_at_utc", now_utc),
        "updated_at_utc": now_utc,
        "update_count": int(previous_metadata.get("update_count", 0)) + 1,
        "source": source,
        "symbol": to_project_symbol(symbol),
        "market": "A-share",
        "frequency": f"{frequency_minutes}m",
        "timezone": timezone_name,
        "timestamp_meaning": "bar_end",
        "availability_policy": "available_after_bar_end",
        "adjustment": adjustment,
        "volume_unit": volume_unit,
        "amount_unit": amount_unit,
        "canonical_columns": MINUTE_COLUMNS,
        "initial_requested_start": initial_requested_start,
        "last_requested_start": requested_start,
        "last_requested_end": requested_end,
        "previous_rows": int(len(previous)),
        "previous_output_sha256": previous_metadata.get("output_sha256"),
        "fetched_rows": int(len(new_rows)),
        "duplicate_timestamps_replaced": duplicate_timestamps,
        "output_rows": int(len(output)),
        "trading_days": int(len(counts_by_day)),
        "datetime_start": output["datetime"].iloc[0],
        "datetime_end": output["datetime"].iloc[-1],
        "expected_rows_per_full_trading_day": expected_rows,
        "incomplete_trading_days": incomplete_days,
        "output_sha256": _sha256(target_path),
        "warnings": warnings,
    }
    temporary_metadata = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_metadata.replace(metadata_path)

    return MinuteArchiveResult(
        output_path=target_path,
        metadata_path=metadata_path,
        fetched_rows=len(new_rows),
        previous_rows=len(previous),
        output_rows=len(output),
        duplicate_timestamps_replaced=duplicate_timestamps,
        trading_days=len(counts_by_day),
    )


def _parse_baostock_datetime(date_values: pd.Series, time_values: pd.Series) -> pd.Series:
    date_digits = date_values.astype(str).str.replace(r"\D", "", regex=True).str.slice(0, 8)
    time_digits = time_values.astype(str).str.replace(r"\D", "", regex=True)
    embedded_datetime = time_digits.str.slice(0, 14)
    combined_datetime = date_digits + time_digits.str.slice(0, 6).str.zfill(6)
    candidates = embedded_datetime.where(time_digits.str.len() >= 14, combined_datetime)
    parsed = pd.to_datetime(candidates, format="%Y%m%d%H%M%S", errors="coerce")
    return parsed.dt.tz_localize(MARKET_TIMEZONE)


def _coerce_market_datetime(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if not isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_localize(ZoneInfo(MARKET_TIMEZONE))
    return parsed.dt.tz_convert(ZoneInfo(MARKET_TIMEZONE))


def _validate_market_relationships(frame: pd.DataFrame) -> None:
    invalid = (
        (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (frame[["volume", "amount"]] < 0).any(axis=1)
        | (frame["high"] < frame[["open", "low", "close"]].max(axis=1))
        | (frame["low"] > frame[["open", "high", "close"]].min(axis=1))
    )
    if invalid.any():
        examples = frame.index[invalid].tolist()[:5]
        raise ValueError(f"Minute data contains invalid OHLC/volume relationships at rows: {examples}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
