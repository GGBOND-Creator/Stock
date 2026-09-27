from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


NUMERIC_COLUMNS = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Segment an A-share spot snapshot.")
    parser.add_argument("--input", default="data/realtime/a_share_spot.csv", help="Spot snapshot CSV.")
    parser.add_argument("--output", default="reports/a_share_segments.csv", help="Segmented CSV output.")
    parser.add_argument("--summary", default="reports/a_share_segments.md", help="Markdown summary output.")
    return parser.parse_args()


def load_spot(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Spot snapshot not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    required = {"symbol", "name", "pct_change", "amount", "total_market_value"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Spot snapshot is missing required columns: {missing}")

    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def board_label(symbol: object) -> str:
    value = str(symbol)
    code = value.split(".", 1)[0]
    suffix = value.rsplit(".", 1)[-1] if "." in value else ""
    if suffix == "BJ":
        return "beijing"
    if code.startswith("688"):
        return "star_market"
    if code.startswith(("300", "301")):
        return "chinext"
    if code.startswith(("002", "003")):
        return "sz_sme_main"
    if suffix == "SZ":
        return "sz_main"
    if suffix == "SH":
        return "sh_main"
    return "other"


def pct_bucket(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value >= 19.5:
        return "limit_up_20pct"
    if value >= 9.5:
        return "limit_up_10pct"
    if value >= 5:
        return "strong_up"
    if value >= 1:
        return "mild_up"
    if value > -1:
        return "flat"
    if value > -5:
        return "mild_down"
    if value > -9.5:
        return "strong_down"
    return "limit_down_area"


def market_cap_bucket(value: float) -> str:
    if pd.isna(value) or value <= 0:
        return "unknown"
    if value < 5_000_000_000:
        return "micro_cap"
    if value < 20_000_000_000:
        return "small_cap"
    if value < 100_000_000_000:
        return "mid_cap"
    return "large_cap"


def valuation_bucket(pe: float) -> str:
    if pd.isna(pe):
        return "unknown"
    if pe <= 0:
        return "loss_or_negative_pe"
    if pe < 15:
        return "low_pe"
    if pe < 35:
        return "mid_pe"
    if pe < 80:
        return "high_pe"
    return "very_high_pe"


def liquidity_bucket(amount: float) -> str:
    if pd.isna(amount) or amount <= 0:
        return "unknown"
    if amount >= 1_000_000_000:
        return "very_active"
    if amount >= 300_000_000:
        return "active"
    if amount >= 50_000_000:
        return "normal"
    return "thin"


def volume_signal(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value >= 3:
        return "volume_spike"
    if value >= 1.5:
        return "elevated_volume"
    if value >= 0.8:
        return "normal_volume"
    return "quiet_volume"


def composite_segment(row: pd.Series) -> str:
    if row["pct_bucket"].startswith("limit_up") and row["liquidity_bucket"] in {"very_active", "active"}:
        return "hot_breakout"
    if row["pct_bucket"] in {"strong_up", "mild_up"} and row["volume_signal"] in {"volume_spike", "elevated_volume"}:
        return "rising_with_volume"
    if row["pct_bucket"] in {"strong_down", "limit_down_area"} and row["liquidity_bucket"] in {"very_active", "active"}:
        return "heavy_selloff"
    if row["market_cap_bucket"] == "large_cap" and row["valuation_bucket"] in {"low_pe", "mid_pe"}:
        return "large_cap_value"
    if row["market_cap_bucket"] in {"micro_cap", "small_cap"} and row["valuation_bucket"] in {"high_pe", "very_high_pe"}:
        return "small_cap_high_valuation"
    if row["liquidity_bucket"] == "thin":
        return "thin_liquidity"
    return "baseline"


def add_segments(frame: pd.DataFrame) -> pd.DataFrame:
    segmented = frame.copy()
    segmented["board"] = segmented["symbol"].map(board_label)
    segmented["pct_bucket"] = segmented["pct_change"].map(pct_bucket)
    segmented["market_cap_bucket"] = segmented["total_market_value"].map(market_cap_bucket)
    segmented["valuation_bucket"] = segmented.get("pe_dynamic", pd.Series(index=segmented.index)).map(valuation_bucket)
    segmented["liquidity_bucket"] = segmented["amount"].map(liquidity_bucket)
    segmented["volume_signal"] = segmented.get("volume_ratio", pd.Series(index=segmented.index)).map(volume_signal)
    segmented["segment"] = segmented.apply(composite_segment, axis=1)
    return segmented


def count_table(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    counts = frame[column].value_counts(dropna=False).rename_axis(column).reset_index(name="count")
    counts["share"] = counts["count"] / len(frame)
    return counts


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_money_yuan(value: float) -> str:
    if pd.isna(value):
        return ""
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.2f}万"
    return f"{value:.2f}"


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    view = frame.loc[:, columns].copy()
    if limit is not None:
        view = view.head(limit)
    for column in ["share"]:
        if column in view.columns:
            view[column] = view[column].map(format_percent)
    for column in ["amount", "total_market_value", "free_float_market_value"]:
        if column in view.columns:
            view[column] = view[column].map(format_money_yuan)
    return view.to_markdown(index=False)


def write_summary(frame: pd.DataFrame, path: str | Path) -> Path:
    summary_path = Path(path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    fetched_at = frame["fetched_at"].dropna().iloc[0] if "fetched_at" in frame and frame["fetched_at"].notna().any() else ""
    top_columns = ["symbol", "name", "pct_change", "amount", "turnover_rate", "volume_ratio", "segment"]
    lines = [
        "# A-share spot segmentation",
        "",
        f"- Snapshot time: {fetched_at}",
        f"- Universe size: {len(frame)}",
        f"- Median pct_change: {frame['pct_change'].median():.2f}%",
        f"- Up / flat / down: {(frame['pct_change'] > 0).sum()} / {(frame['pct_change'] == 0).sum()} / {(frame['pct_change'] < 0).sum()}",
        "",
        "## By board",
        "",
        markdown_table(count_table(frame, "board"), ["board", "count", "share"]),
        "",
        "## By momentum",
        "",
        markdown_table(count_table(frame, "pct_bucket"), ["pct_bucket", "count", "share"]),
        "",
        "## By market cap",
        "",
        markdown_table(count_table(frame, "market_cap_bucket"), ["market_cap_bucket", "count", "share"]),
        "",
        "## By valuation",
        "",
        markdown_table(count_table(frame, "valuation_bucket"), ["valuation_bucket", "count", "share"]),
        "",
        "## By liquidity",
        "",
        markdown_table(count_table(frame, "liquidity_bucket"), ["liquidity_bucket", "count", "share"]),
        "",
        "## Composite segments",
        "",
        markdown_table(count_table(frame, "segment"), ["segment", "count", "share"]),
        "",
        "## Top gainers by active trading",
        "",
        markdown_table(
            frame.sort_values(["pct_change", "amount"], ascending=[False, False]),
            top_columns,
            limit=20,
        ),
        "",
        "## Top active selloffs",
        "",
        markdown_table(
            frame.sort_values(["pct_change", "amount"], ascending=[True, False]),
            top_columns,
            limit=20,
        ),
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8-sig")
    return summary_path


def main() -> None:
    args = parse_args()
    frame = add_segments(load_spot(args.input))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    summary_path = write_summary(frame, args.summary)

    print(f"Rows: {len(frame)}")
    print(f"Saved segmented CSV: {output_path}")
    print(f"Saved summary: {summary_path}")
    print(count_table(frame, "segment").to_string(index=False))


if __name__ == "__main__":
    main()
