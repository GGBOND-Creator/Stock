from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_IFIND_INDICATORS = ["open", "high", "low", "latest", "volume", "amount"]


@dataclass(frozen=True)
class RealtimeConfig:
    provider: str = "ifind"
    username: str | None = None
    password: str | None = None
    ifind_path: str | None = None
    params: str = ""
    login: bool = True


def fetch_realtime_quotes(
    symbols: Iterable[str],
    indicators: Iterable[str] | None = None,
    config: RealtimeConfig | None = None,
) -> pd.DataFrame:
    """Fetch realtime quotes from a local market-data provider."""
    config = config or RealtimeConfig()
    provider = config.provider.lower()
    if provider != "ifind":
        raise ValueError(f"Unsupported realtime provider: {config.provider}")
    return fetch_ifind_realtime(symbols, indicators=indicators, config=config)


def fetch_ifind_realtime(
    symbols: Iterable[str],
    indicators: Iterable[str] | None = None,
    config: RealtimeConfig | None = None,
) -> pd.DataFrame:
    """Fetch realtime quotes through the TongHuaShun iFinD Python interface.

    This requires the local TongHuaShun data interface/iFinD environment to
    provide the `iFinDPy` module. Yuanhang terminal cache files are intentionally
    not parsed here because their local formats vary by version and are not a
    stable API.
    """
    config = config or RealtimeConfig()
    symbol_list = _normalize_symbols(symbols)
    indicator_list = list(indicators or DEFAULT_IFIND_INDICATORS)

    ths = _import_ifind(config.ifind_path)
    if config.login:
        _login_ifind(ths, config)

    response = ths.THS_RQ(
        ",".join(symbol_list),
        ";".join(indicator_list),
        config.params,
    )
    frame = _ifind_response_to_frame(response, symbol_list, indicator_list)
    frame.insert(0, "fetched_at", datetime.now().isoformat(timespec="seconds"))
    return frame


def save_realtime_quotes(frame: pd.DataFrame, output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _import_ifind(ifind_path: str | None = None):
    module_path = ifind_path or os.getenv("IFINDPY_PATH")
    if module_path:
        import sys

        sys.path.insert(0, str(Path(module_path).expanduser()))

    try:
        import iFinDPy as ths
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import iFinDPy. Install or enable the local TongHuaShun "
            "iFinD/Quant API Python environment first, pass --ifind-path, "
            "or set IFINDPY_PATH to the directory containing iFinDPy."
        ) from exc
    return ths


def _login_ifind(ths, config: RealtimeConfig) -> None:
    username = config.username or os.getenv("THS_USERNAME")
    password = config.password or os.getenv("THS_PASSWORD")
    if not username or not password:
        return

    result = ths.THS_iFinDLogin(username, password)
    if result not in (0, "0", None):
        raise RuntimeError(f"THS_iFinDLogin failed with code: {result}")


def _ifind_response_to_frame(response, symbols: list[str], indicators: list[str]) -> pd.DataFrame:
    error_code = getattr(response, "errorcode", 0)
    if error_code not in (0, "0", None):
        message = getattr(response, "errmsg", "")
        raise RuntimeError(f"THS_RQ failed: {error_code} {message}".strip())

    data = getattr(response, "data", response)
    if isinstance(data, pd.DataFrame):
        frame = data.copy()
    elif isinstance(data, dict):
        frame = pd.DataFrame(data)
    else:
        frame = pd.DataFrame(data)

    if frame.empty:
        return _empty_quote_frame(indicators)

    frame.columns = [str(column).strip() for column in frame.columns]
    frame = _ensure_symbol_column(frame, symbols)
    return _normalize_quote_columns(frame)


def _ensure_symbol_column(frame: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    lower_map = {column.lower(): column for column in frame.columns}
    if "symbol" in lower_map:
        return frame.rename(columns={lower_map["symbol"]: "symbol"})
    for candidate in ["thscode", "ths_code", "code", "securitycode"]:
        if candidate in lower_map:
            return frame.rename(columns={lower_map[candidate]: "symbol"})
    if len(frame) == len(symbols):
        frame = frame.copy()
        frame.insert(0, "symbol", symbols)
    return frame


def _normalize_quote_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in frame.columns:
        normalized = column.strip().lower().replace(" ", "").replace("_", "")
        if normalized in {"latest", "last", "price", "newprice", "close"}:
            rename_map[column] = "price"
        elif normalized in {"vol", "volume", "tradevolume"}:
            rename_map[column] = "volume"
        elif normalized in {"amt", "amount", "turnover"}:
            rename_map[column] = "amount"
        elif normalized in {"op", "open"}:
            rename_map[column] = "open"
        elif normalized in {"hi", "high"}:
            rename_map[column] = "high"
        elif normalized in {"lo", "low"}:
            rename_map[column] = "low"
    frame = frame.rename(columns=rename_map)
    for column in ["open", "high", "low", "price", "volume", "amount"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="ignore")
    return frame


def _empty_quote_frame(indicators: list[str]) -> pd.DataFrame:
    columns = ["symbol"] + list(indicators)
    return pd.DataFrame(columns=columns)


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    symbol_list = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
    if not symbol_list:
        raise ValueError("Provide at least one symbol, for example: 000001.SZ")
    return symbol_list
