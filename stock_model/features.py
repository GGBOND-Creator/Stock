from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    "ret_20",
    "ma_5_gap",
    "ma_10_gap",
    "ma_20_gap",
    "ma_60_gap",
    "volatility_10",
    "volatility_20",
    "volume_change_5",
    "volume_change_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "bb_position_20",
]


def add_features(prices: pd.DataFrame, horizon: int = 1, threshold: float = 0.0) -> pd.DataFrame:
    frame = prices.copy()
    close = frame["close"]
    volume = frame["volume"].replace(0, np.nan)

    frame["ret_1"] = close.pct_change()
    for window in [3, 5, 10, 20]:
        frame[f"ret_{window}"] = close.pct_change(window)

    for window in [5, 10, 20, 60]:
        moving_average = close.rolling(window).mean()
        frame[f"ma_{window}_gap"] = close / moving_average - 1

    for window in [10, 20]:
        frame[f"volatility_{window}"] = frame["ret_1"].rolling(window).std()

    for window in [5, 20]:
        frame[f"volume_change_{window}"] = volume / volume.rolling(window).mean() - 1

    frame["rsi_14"] = _rsi(close, 14)
    frame["macd"], frame["macd_signal"] = _macd(close)
    frame["bb_position_20"] = _bollinger_position(close, 20)

    future_return = close.shift(-horizon) / close - 1
    frame["future_return"] = future_return
    frame["target"] = np.where(future_return.notna(), future_return > threshold, np.nan)

    model_frame = frame.dropna(subset=FEATURE_COLUMNS + ["future_return", "target"]).reset_index(drop=True)
    model_frame["target"] = model_frame["target"].astype(int)
    return model_frame


def add_latest_features(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    close = frame["close"]
    volume = frame["volume"].replace(0, np.nan)

    frame["ret_1"] = close.pct_change()
    for window in [3, 5, 10, 20]:
        frame[f"ret_{window}"] = close.pct_change(window)

    for window in [5, 10, 20, 60]:
        moving_average = close.rolling(window).mean()
        frame[f"ma_{window}_gap"] = close / moving_average - 1

    for window in [10, 20]:
        frame[f"volatility_{window}"] = frame["ret_1"].rolling(window).std()

    for window in [5, 20]:
        frame[f"volume_change_{window}"] = volume / volume.rolling(window).mean() - 1

    frame["rsi_14"] = _rsi(close, 14)
    frame["macd"], frame["macd_signal"] = _macd(close)
    frame["bb_position_20"] = _bollinger_position(close, 20)
    return frame.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    return frame[FEATURE_COLUMNS], frame["target"].astype(int)


def _rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema_12 = series.ewm(span=12, adjust=False).mean()
    ema_26 = series.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def _bollinger_position(series: pd.Series, window: int) -> pd.Series:
    moving_average = series.rolling(window).mean()
    std = series.rolling(window).std()
    upper = moving_average + 2 * std
    lower = moving_average - 2 * std
    return (series - lower) / (upper - lower)
