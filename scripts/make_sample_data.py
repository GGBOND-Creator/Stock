from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic OHLCV sample data.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed used for repeatable sample data.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    dates = pd.bdate_range("2020-01-01", periods=900)
    drift = 0.00025
    cyclical = 0.002 * np.sin(np.arange(len(dates)) / 24)
    shocks = rng.normal(0, 0.015, len(dates))
    returns = drift + cyclical + shocks
    close = 100 * np.cumprod(1 + returns)

    open_price = close * (1 + rng.normal(0, 0.004, len(dates)))
    high = np.maximum(open_price, close) * (1 + rng.uniform(0.001, 0.018, len(dates)))
    low = np.minimum(open_price, close) * (1 - rng.uniform(0.001, 0.018, len(dates)))
    volume = rng.integers(800_000, 4_000_000, len(dates))

    frame = pd.DataFrame(
        {
            "date": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )

    output = Path("data/raw/SAMPLE.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    print(f"Saved sample data: {output}")


if __name__ == "__main__":
    main()
