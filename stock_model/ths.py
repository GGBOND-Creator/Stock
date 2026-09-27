from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "date": ["date", "日期", "时间", "交易日期"],
    "open": ["open", "开盘", "开盘价"],
    "high": ["high", "最高", "最高价"],
    "low": ["low", "最低", "最低价"],
    "close": ["close", "收盘", "收盘价"],
    "volume": ["volume", "vol", "成交量", "成交量(手)", "成交量（手）"],
}


def load_ths_export(path: str | Path) -> pd.DataFrame:
    """Load a TongHuaShun exported CSV/TXT file and normalize it to OHLCV."""
    export_path = Path(path)
    if not export_path.exists():
        raise FileNotFoundError(f"同花顺导出文件不存在: {export_path}")

    text = _read_text(export_path)
    table_text = _slice_to_header(text)
    frame = pd.read_csv(StringIO(table_text), sep=None, engine="python")
    frame.columns = [_normalize_name(column) for column in frame.columns]
    frame = frame.rename(columns=_build_rename_map(frame.columns))

    missing = [column for column in ["date", "open", "high", "low", "close", "volume"] if column not in frame.columns]
    if missing:
        raise ValueError(f"无法识别同花顺导出文件列: {missing}; 当前列: {list(frame.columns)}")

    normalized = frame[["date", "open", "high", "low", "close", "volume"]].copy()
    normalized["date"] = pd.to_datetime(normalized["date"].astype(str).str.strip(), errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        normalized[column] = _to_number(normalized[column])

    normalized = normalized.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    normalized = normalized.sort_values("date").drop_duplicates("date", keep="last")
    return normalized.reset_index(drop=True)


def import_ths_export(path: str | Path, symbol: str | None = None, output_dir: str | Path = "data/raw") -> Path:
    frame = load_ths_export(path)
    export_path = Path(path)
    output_symbol = symbol or export_path.stem
    output_path = Path(output_dir) / f"{output_symbol}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def _read_text(path: Path) -> str:
    for encoding in ["utf-8-sig", "gb18030", "gbk"]:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _slice_to_header(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        normalized = _normalize_name(line)
        if ("日期" in normalized or "date" in normalized) and ("收盘" in normalized or "close" in normalized):
            return "\n".join(lines[index:])
    return "\n".join(lines)


def _build_rename_map(columns: pd.Index) -> dict[str, str]:
    rename_map = {}
    for target, aliases in COLUMN_ALIASES.items():
        for column in columns:
            if column in [_normalize_name(alias) for alias in aliases]:
                rename_map[column] = target
                break
    return rename_map


def _normalize_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def _to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("--", "", regex=False)
        .str.replace("万", "e4", regex=False)
        .str.replace("亿", "e8", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")
