from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def load_price_csv(path: str | Path) -> pd.DataFrame:
    """Load an OHLCV CSV and normalize column names."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    frame = frame[REQUIRED_COLUMNS].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=REQUIRED_COLUMNS)
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame = frame.reset_index(drop=True)
    return frame


def download_prices(symbol: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Download prices with yfinance, if available."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install yfinance or provide a local CSV file.") from exc

    data = yf.download(symbol, start=start, end=end, auto_adjust=False, progress=False)
    if data.empty:
        raise ValueError(f"No data downloaded for symbol: {symbol}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [column[0] for column in data.columns]

    data = data.reset_index()
    data = data.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return data[REQUIRED_COLUMNS].dropna().reset_index(drop=True)


def save_raw_prices(frame: pd.DataFrame, symbol: str, directory: str | Path = "data/raw") -> Path:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol}.csv"
    frame.to_csv(output_path, index=False)
    return output_path
