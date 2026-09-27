from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd

from stock_model.data import load_price_csv
from stock_model.features import add_latest_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict the latest stock trend probability.")
    parser.add_argument("--csv", required=True, help="Path to local OHLCV CSV.")
    parser.add_argument("--model", required=True, help="Path to trained .joblib model.")
    parser.add_argument("--output", default=None, help="Optional CSV path for the prediction row.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = joblib.load(args.model)
    prices = load_price_csv(args.csv)
    frame = add_latest_features(prices)

    latest = frame.iloc[[-1]].copy()
    X_latest = latest[bundle["feature_columns"]]
    probability_up = float(bundle["pipeline"].predict_proba(X_latest)[:, 1][0])
    prediction = int(probability_up >= 0.5)

    result = pd.DataFrame(
        [
            {
                "symbol": bundle.get("symbol", Path(args.csv).stem),
                "date": latest["date"].iloc[0],
                "close": latest["close"].iloc[0],
                "prob_up": probability_up,
                "prediction": "up" if prediction else "down",
            }
        ]
    )

    print(result.to_string(index=False))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
        print(f"Saved prediction: {output_path}")


if __name__ == "__main__":
    main()
