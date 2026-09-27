from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def fetch_akshare_spot() -> pd.DataFrame:
    """Fetch current A-share market snapshot with AkShare."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("Install akshare first: pip install akshare") from exc

    frame = ak.stock_zh_a_spot_em()
    if frame.empty:
        raise ValueError("AkShare returned an empty A-share spot snapshot.")

    rename_map = {
        "代码": "symbol",
        "名称": "name",
        "最新价": "price",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "成交量": "volume",
        "成交额": "amount",
        "今开": "open",
        "最高": "high",
        "最低": "low",
        "昨收": "prev_close",
        "换手率": "turnover_rate",
        "量比": "volume_ratio",
        "市盈率-动态": "pe_dynamic",
        "市净率": "pb",
        "总市值": "total_market_value",
        "流通市值": "free_float_market_value",
    }
    normalized = frame.rename(columns=rename_map)
    normalized["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    normalized["symbol"] = normalized["symbol"].map(to_project_symbol)

    preferred = [
        "fetched_at",
        "symbol",
        "name",
        "price",
        "pct_change",
        "change",
        "open",
        "high",
        "low",
        "prev_close",
        "volume",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "pe_dynamic",
        "pb",
        "total_market_value",
        "free_float_market_value",
    ]
    columns = [column for column in preferred if column in normalized.columns]
    normalized = normalized[columns].copy()
    return _coerce_numeric(normalized, skip={"fetched_at", "symbol", "name"})


def fetch_akshare_history(
    symbol: str,
    start: str = "20180101",
    end: str | None = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """Fetch daily A-share history with AkShare and return standard OHLCV."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("Install akshare first: pip install akshare") from exc

    raw_symbol = to_raw_a_share_code(symbol)
    end_date = end or date.today().strftime("%Y%m%d")
    frame = ak.stock_zh_a_hist(
        symbol=raw_symbol,
        period="daily",
        start_date=start,
        end_date=end_date,
        adjust=adjust,
    )
    if frame.empty:
        raise ValueError(f"AkShare returned no history for {symbol}.")
    return normalize_akshare_history(frame)


def fetch_baostock_history(
    symbol: str,
    start: str = "2018-01-01",
    end: str | None = None,
    adjustflag: str = "2",
) -> pd.DataFrame:
    """Fetch daily A-share history with BaoStock and return standard OHLCV."""
    try:
        import baostock as bs
    except ImportError as exc:
        raise RuntimeError("Install baostock first: pip install baostock") from exc

    bs_symbol = to_baostock_symbol(symbol)
    end_date = end or date.today().isoformat()
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")

    try:
        query = bs.query_history_k_data_plus(
            bs_symbol,
            "date,code,open,high,low,close,volume,amount",
            start_date=start,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag,
        )
        if query.error_code != "0":
            raise RuntimeError(f"BaoStock query failed: {query.error_code} {query.error_msg}")

        rows = []
        while query.next():
            rows.append(query.get_row_data())
        frame = pd.DataFrame(rows, columns=query.fields)
    finally:
        bs.logout()

    if frame.empty:
        raise ValueError(f"BaoStock returned no history for {symbol}.")
    return normalize_baostock_history(frame)


def normalize_akshare_history(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    )
    return _standardize_ohlcv(renamed)


def normalize_baostock_history(frame: pd.DataFrame) -> pd.DataFrame:
    return _standardize_ohlcv(frame)


def save_frame(frame: pd.DataFrame, output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def to_project_symbol(symbol: object) -> str:
    value = str(symbol).strip()
    if value.endswith((".SH", ".SZ", ".BJ")):
        return value
    if value.startswith(("sh.", "sz.", "bj.")):
        return f"{value[3:]}.{value[:2].upper()}"
    if value.startswith("6"):
        return f"{value}.SH"
    if value.startswith(("0", "3")):
        return f"{value}.SZ"
    if value.startswith(("4", "8", "9")):
        return f"{value}.BJ"
    return value


def to_raw_a_share_code(symbol: str) -> str:
    value = str(symbol).strip()
    if "." in value:
        head, tail = value.split(".", 1)
        if tail.upper() in {"SH", "SZ", "BJ"}:
            return head
    if value.startswith(("sh.", "sz.", "bj.")):
        return value[3:]
    return value


def to_baostock_symbol(symbol: str) -> str:
    value = to_project_symbol(symbol)
    if value.endswith(".SH"):
        return f"sh.{value[:-3]}"
    if value.endswith(".SZ"):
        return f"sz.{value[:-3]}"
    if value.endswith(".BJ"):
        return f"bj.{value[:-3]}"
    raise ValueError(f"Cannot infer BaoStock market prefix for symbol: {symbol}")


def _standardize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns after normalization: {missing}")

    normalized = frame[OHLCV_COLUMNS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=OHLCV_COLUMNS)
    normalized = normalized.sort_values("date").drop_duplicates("date", keep="last")
    return normalized.reset_index(drop=True)


def _coerce_numeric(frame: pd.DataFrame, skip: set[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.columns:
        if column not in skip:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized
