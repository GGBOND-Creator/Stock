from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from stock_model.data import download_prices, load_price_csv, save_raw_prices
from stock_model.features import add_features, split_features_target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a stock trend classifier.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="Path to local OHLCV CSV.")
    source.add_argument("--download", help="Symbol to download with yfinance.")
    parser.add_argument("--start", default="2018-01-01", help="Download start date.")
    parser.add_argument("--end", default=None, help="Download end date.")
    parser.add_argument("--symbol", default=None, help="Symbol name used for outputs.")
    parser.add_argument("--horizon", type=int, default=1, help="Prediction horizon in trading days.")
    parser.add_argument("--threshold", type=float, default=0.0, help="Future return threshold for positive class.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Final chronological test fraction.")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed used by the classifier.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = args.symbol or args.download or Path(args.csv).stem

    if args.download:
        prices = download_prices(args.download, start=args.start, end=args.end)
        raw_path = save_raw_prices(prices, symbol)
        print(f"Saved downloaded data: {raw_path}")
    else:
        prices = load_price_csv(args.csv)

    frame = add_features(prices, horizon=args.horizon, threshold=args.threshold)
    if len(frame) < 120:
        raise ValueError("Not enough rows after feature generation. Provide at least 180 daily bars if possible.")

    X, y = split_features_target(frame)
    split_index = int(len(frame) * (1 - args.test_size))
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    pipeline = Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=200,
                    learning_rate=0.04,
                    max_leaf_nodes=15,
                    random_state=args.random_state,
                ),
            ),
        ]
    )

    cv_scores = cross_validate_time_series(pipeline, X_train, y_train)
    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    accuracy = accuracy_score(y_test, predictions)
    auc = roc_auc_score(y_test, probabilities) if y_test.nunique() == 2 else float("nan")

    Path("models").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    model_path = Path("models") / f"{symbol}_model.joblib"
    joblib.dump(
        {
            "pipeline": pipeline,
            "symbol": symbol,
            "horizon": args.horizon,
            "threshold": args.threshold,
            "feature_columns": list(X.columns),
        },
        model_path,
    )

    test_report = frame.iloc[split_index:][["date", "close", "future_return", "target"]].copy()
    test_report["prob_up"] = probabilities
    test_report["prediction"] = predictions
    test_report["strategy_return"] = test_report["future_return"] * (test_report["prob_up"] >= 0.55)
    report_path = Path("reports") / f"{symbol}_test_predictions.csv"
    test_report.to_csv(report_path, index=False)

    plot_path = Path("reports") / f"{symbol}_backtest.png"
    save_backtest_plot(test_report, plot_path)

    print(f"Rows used: {len(frame)}")
    print(f"CV accuracy scores: {', '.join(f'{score:.3f}' for score in cv_scores)}")
    print(f"Test accuracy: {accuracy:.3f}")
    print(f"Test ROC AUC: {auc:.3f}")
    print(classification_report(y_test, predictions, digits=3))
    print(f"Saved model: {model_path}")
    print(f"Saved predictions: {report_path}")
    print(f"Saved backtest plot: {plot_path}")


def cross_validate_time_series(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> list[float]:
    splitter = TimeSeriesSplit(n_splits=5)
    scores = []
    for train_index, valid_index in splitter.split(X):
        X_train, X_valid = X.iloc[train_index], X.iloc[valid_index]
        y_train, y_valid = y.iloc[train_index], y.iloc[valid_index]
        pipeline.fit(X_train, y_train)
        scores.append(accuracy_score(y_valid, pipeline.predict(X_valid)))
    return scores


def save_backtest_plot(report: pd.DataFrame, path: Path) -> None:
    strategy_curve = (1 + report["strategy_return"].fillna(0)).cumprod()
    buy_hold_curve = (1 + report["future_return"].fillna(0)).cumprod()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(report["date"], buy_hold_curve, label="Buy and hold")
    ax.plot(report["date"], strategy_curve, label="Prob > 0.55 strategy")
    ax.set_title("Simple out-of-sample backtest")
    ax.set_xlabel("Date")
    ax.set_ylabel("Growth of 1.0")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
