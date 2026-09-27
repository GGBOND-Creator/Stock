from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd


CANONICAL_COLUMNS = ["date", "open", "high", "low", "close", "volume"]

COLUMN_ALIASES = {
    "date": ["date", "datetime", "timestamp", "time", "日期", "时间", "交易日期", "交易时间"],
    "open": ["open", "openprice", "开盘", "开盘价"],
    "high": ["high", "highprice", "最高", "最高价"],
    "low": ["low", "lowprice", "最低", "最低价"],
    "close": ["close", "closeprice", "last", "price", "收盘", "收盘价", "最新价"],
    "volume": [
        "volume",
        "vol",
        "成交量",
        "成交量手",
        "成交量股",
        "成交量(手)",
        "成交量（手）",
        "成交量(股)",
        "成交量（股）",
    ],
}


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    metadata_path: Path
    input_rows: int
    output_rows: int
    dropped_rows: int
    duplicate_dates: int


def convert_market_csv(
    input_path: str | Path,
    output_path: str | Path,
    *,
    source: str,
    symbol: str,
    market: str = "unknown",
    frequency: str = "1d",
    adjustment: str = "unknown",
    volume_unit: str = "source_native",
    column_mapping: Mapping[str, str] | None = None,
    date_format: str | None = None,
    strict: bool = True,
) -> ConversionResult:
    """Convert an external CSV/TXT table to the project's canonical OHLCV CSV.

    ``column_mapping`` maps canonical names to source names, for example
    ``{"date": "交易日期", "close": "收盘价"}``. Unmapped columns are inferred
    from common Chinese and English aliases.
    """
    source_path = Path(input_path)
    target_path = Path(output_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Input data file not found: {source_path}")
    if not source.strip():
        raise ValueError("source must not be empty")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if frequency != "1d":
        raise ValueError(
            f"Only daily bars (frequency='1d') are supported by schema ohlcv_daily_v1; got {frequency!r}."
        )

    raw, encoding = _read_table(source_path)
    if raw.empty:
        raise ValueError(f"Input data file is empty: {source_path}")

    resolved = _resolve_columns(raw.columns, column_mapping or {})
    normalized = pd.DataFrame(index=raw.index)
    normalized["date"] = _to_datetime(raw[resolved["date"]], date_format=date_format)
    for column in ["open", "high", "low", "close", "volume"]:
        normalized[column] = _to_number(raw[resolved[column]])

    input_rows = len(normalized)
    parse_invalid = normalized[CANONICAL_COLUMNS].isna().any(axis=1)
    parsed = normalized.loc[~parse_invalid].copy()

    duplicate_dates = int(parsed.duplicated("date", keep="last").sum())
    parsed = parsed.sort_values("date").drop_duplicates("date", keep="last")

    price_invalid = (
        (parsed[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (parsed["volume"] < 0)
        | (parsed["high"] < parsed[["open", "low", "close"]].max(axis=1))
        | (parsed["low"] > parsed[["open", "high", "close"]].min(axis=1))
    )
    invalid_market_rows = int(price_invalid.sum())
    if strict and invalid_market_rows:
        examples = [int(index) + 2 for index in parsed.index[price_invalid][:5]]
        raise ValueError(
            "Found invalid OHLCV relationships or negative values in source rows "
            f"{examples}. Fix the source data or rerun with strict=False to drop them."
        )
    parsed = parsed.loc[~price_invalid].reset_index(drop=True)
    if parsed.empty:
        raise ValueError("No valid OHLCV rows remain after conversion.")

    dropped_rows = input_rows - len(parsed)
    warnings = []
    parse_invalid_count = int(parse_invalid.sum())
    if parse_invalid_count:
        warnings.append(f"Dropped {parse_invalid_count} rows with missing or unparseable values.")
    if duplicate_dates:
        warnings.append(f"Kept the last row for {duplicate_dates} duplicate dates.")
    if invalid_market_rows:
        warnings.append(f"Dropped {invalid_market_rows} rows with invalid OHLCV relationships.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    output = parsed[CANONICAL_COLUMNS].copy()
    output["date"] = output["date"].dt.strftime("%Y-%m-%d")
    output.to_csv(target_path, index=False, encoding="utf-8")

    metadata_path = target_path.with_suffix(target_path.suffix + ".meta.json")
    metadata = {
        "schema_version": "ohlcv_daily_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "symbol": symbol,
        "market": market,
        "frequency": frequency,
        "adjustment": adjustment,
        "volume_unit": volume_unit,
        "input_file": source_path.name,
        "input_sha256": _sha256(source_path),
        "input_encoding": encoding,
        "output_file": target_path.name,
        "canonical_columns": CANONICAL_COLUMNS,
        "resolved_columns": resolved,
        "input_rows": input_rows,
        "output_rows": len(output),
        "dropped_rows": dropped_rows,
        "duplicate_dates": duplicate_dates,
        "date_start": output["date"].iloc[0],
        "date_end": output["date"].iloc[-1],
        "warnings": warnings,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return ConversionResult(
        output_path=target_path,
        metadata_path=metadata_path,
        input_rows=input_rows,
        output_rows=len(output),
        dropped_rows=dropped_rows,
        duplicate_dates=duplicate_dates,
    )


def _read_table(path: Path) -> tuple[pd.DataFrame, str]:
    errors = []
    for encoding in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError(f"Could not decode {path}. Tried common encodings: {'; '.join(errors)}")


def _resolve_columns(columns: pd.Index, mapping: Mapping[str, str]) -> dict[str, str]:
    unknown_targets = sorted(set(mapping) - set(CANONICAL_COLUMNS))
    if unknown_targets:
        raise ValueError(f"Unknown canonical mapping targets: {unknown_targets}")

    normalized_sources = {_normalize_name(column): str(column) for column in columns}
    resolved: dict[str, str] = {}
    for target in CANONICAL_COLUMNS:
        requested = mapping.get(target)
        if requested is not None:
            source_name = normalized_sources.get(_normalize_name(requested))
            if source_name is None:
                raise ValueError(f"Mapped source column not found: {requested!r}; columns={list(columns)}")
            resolved[target] = source_name
            continue

        for alias in COLUMN_ALIASES[target]:
            source_name = normalized_sources.get(_normalize_name(alias))
            if source_name is not None:
                resolved[target] = source_name
                break

    missing = [column for column in CANONICAL_COLUMNS if column not in resolved]
    if missing:
        raise ValueError(
            f"Could not infer required columns {missing}; source columns={list(columns)}. "
            "Provide explicit column mappings."
        )
    if len(set(resolved.values())) != len(CANONICAL_COLUMNS):
        raise ValueError(f"One source column was mapped to multiple canonical fields: {resolved}")
    return resolved


def _normalize_name(value: object) -> str:
    return re.sub(r"[\s_\-（）()]", "", str(value).strip().lower())


def _to_datetime(series: pd.Series, date_format: str | None) -> pd.Series:
    values = series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(values, format=date_format, errors="coerce")


def _to_number(series: pd.Series) -> pd.Series:
    values = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("，", "", regex=False)
        .str.replace("--", "", regex=False)
        .str.replace("%", "", regex=False)
    )
    suffix = values.str.extract(r"([万亿kKmM])\s*$", expand=False)
    numeric = pd.to_numeric(values.str.replace(r"[万亿kKmM]\s*$", "", regex=True), errors="coerce")
    multipliers = suffix.map({"万": 1e4, "亿": 1e8, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}).fillna(1)
    return numeric * multipliers


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
