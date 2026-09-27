from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two standardized daily OHLCV files.")
    parser.add_argument("--left", required=True, help="First standardized OHLCV CSV.")
    parser.add_argument("--right", required=True, help="Second standardized OHLCV CSV.")
    parser.add_argument("--left-label", default="left", help="Display label for the first source.")
    parser.add_argument("--right-label", default="right", help="Display label for the second source.")
    parser.add_argument("--left-adjustment", default="unknown", help="Declared adjustment for the first source.")
    parser.add_argument("--right-adjustment", default="unknown", help="Declared adjustment for the second source.")
    parser.add_argument("--left-volume-unit", default="unknown", help="Documented volume unit for the first source.")
    parser.add_argument("--right-volume-unit", default="unknown", help="Documented volume unit for the second source.")
    parser.add_argument("--symbol", required=True, help="Project symbol, for example 002714.SZ.")
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="Output path without suffix; .csv, .json, and .md will be added.",
    )
    parser.add_argument(
        "--price-tolerance",
        type=float,
        default=1e-8,
        help="Absolute tolerance used to count matching price rows.",
    )
    return parser.parse_args()


def load_ohlcv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")

    normalized = frame[OHLCV_COLUMNS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    for column in OHLCV_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if normalized[OHLCV_COLUMNS].isna().any().any():
        raise ValueError(f"{path} contains missing or non-numeric OHLCV values.")
    if normalized["date"].duplicated().any():
        raise ValueError(f"{path} contains duplicate dates.")
    return normalized.sort_values("date").reset_index(drop=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_or_none(value: float) -> float | None:
    return None if pd.isna(value) else float(value)


def main() -> None:
    args = parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    left = load_ohlcv(left_path)
    right = load_ohlcv(right_path)
    merged = left.merge(
        right,
        on="date",
        how="outer",
        suffixes=("_left", "_right"),
        indicator="date_status",
        validate="one_to_one",
    ).sort_values("date")

    overlap = merged[merged["date_status"] == "both"].copy()
    for column in PRICE_COLUMNS:
        overlap[f"{column}_diff_left_minus_right"] = overlap[f"{column}_left"] - overlap[f"{column}_right"]

    overlap["max_abs_price_diff"] = overlap[
        [f"{column}_diff_left_minus_right" for column in PRICE_COLUMNS]
    ].abs().max(axis=1)
    valid_volume = (overlap["volume_left"] > 0) & (overlap["volume_right"] > 0)
    overlap["volume_ratio_right_over_left"] = pd.NA
    overlap.loc[valid_volume, "volume_ratio_right_over_left"] = (
        overlap.loc[valid_volume, "volume_right"] / overlap.loc[valid_volume, "volume_left"]
    )
    volume_ratio = pd.to_numeric(overlap["volume_ratio_right_over_left"], errors="coerce")
    observed_factor = finite_or_none(volume_ratio.median())
    if observed_factor and observed_factor > 0:
        overlap["volume_right_scaled_by_observed_factor"] = overlap["volume_right"] / observed_factor
        denominator = overlap["volume_left"].abs().where(overlap["volume_left"] != 0)
        overlap["scaled_volume_relative_diff"] = (
            overlap["volume_right_scaled_by_observed_factor"] - overlap["volume_left"]
        ).abs() / denominator
    else:
        overlap["volume_right_scaled_by_observed_factor"] = pd.NA
        overlap["scaled_volume_relative_diff"] = pd.NA

    only_left = int((merged["date_status"] == "left_only").sum())
    only_right = int((merged["date_status"] == "right_only").sum())
    exact_price_rows = int((overlap["max_abs_price_diff"] <= args.price_tolerance).sum())
    mismatch_dates = overlap.loc[overlap["max_abs_price_diff"] > args.price_tolerance, "date"]
    left_close_return = overlap["close_left"].pct_change()
    right_close_return = overlap["close_right"].pct_change()
    return_abs_diff = (left_close_return - right_close_return).abs()
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "symbol": args.symbol,
        "left": {
            "label": args.left_label,
            "adjustment": args.left_adjustment,
            "volume_unit": args.left_volume_unit,
            "path": left_path.as_posix(),
            "sha256": sha256(left_path),
            "rows": int(len(left)),
            "first_date": left["date"].min().date().isoformat(),
            "last_date": left["date"].max().date().isoformat(),
        },
        "right": {
            "label": args.right_label,
            "adjustment": args.right_adjustment,
            "volume_unit": args.right_volume_unit,
            "path": right_path.as_posix(),
            "sha256": sha256(right_path),
            "rows": int(len(right)),
            "first_date": right["date"].min().date().isoformat(),
            "last_date": right["date"].max().date().isoformat(),
        },
        "date_comparison": {
            "overlap_rows": int(len(overlap)),
            "left_only_rows": only_left,
            "right_only_rows": only_right,
        },
        "price_comparison": {
            "tolerance": args.price_tolerance,
            "all_ohlc_match_rows": exact_price_rows,
            "all_ohlc_match_fraction": float(exact_price_rows / len(overlap)) if len(overlap) else None,
            "last_mismatch_date": mismatch_dates.max().date().isoformat() if len(mismatch_dates) else None,
            "maximum_absolute_difference": {
                column: finite_or_none(overlap[f"{column}_diff_left_minus_right"].abs().max())
                for column in PRICE_COLUMNS
            },
        },
        "close_return_comparison": {
            "correlation": finite_or_none(left_close_return.corr(right_close_return)),
            "median_absolute_difference": finite_or_none(return_abs_diff.median()),
            "maximum_absolute_difference": finite_or_none(return_abs_diff.max()),
        },
        "volume_comparison": {
            "positive_volume_overlap_rows": int(valid_volume.sum()),
            "observed_right_over_left_ratio_median": observed_factor,
            "observed_right_over_left_ratio_min": finite_or_none(volume_ratio.min()),
            "observed_right_over_left_ratio_max": finite_or_none(volume_ratio.max()),
            "scaled_by_median_ratio_relative_diff_median": finite_or_none(
                pd.to_numeric(overlap["scaled_volume_relative_diff"], errors="coerce").median()
            ),
            "scaled_by_median_ratio_relative_diff_max": finite_or_none(
                pd.to_numeric(overlap["scaled_volume_relative_diff"], errors="coerce").max()
            ),
        },
        "interpretation_note": (
            "The observed volume ratio is evidence of a unit-scale difference, not by itself proof of each "
            "provider's declared unit. Confirm provider documentation before assigning unit names."
        ),
    }

    comparison_path = Path(f"{output_prefix}.csv")
    json_path = Path(f"{output_prefix}.json")
    markdown_path = Path(f"{output_prefix}.md")
    overlap.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    max_price_diff = max(
        value or 0.0 for value in summary["price_comparison"]["maximum_absolute_difference"].values()
    )
    markdown = f"""# {args.symbol} 双来源日线核验

生成时间：{summary['generated_at']}

## 输入口径

- 左侧：{args.left_label}，复权 `{args.left_adjustment}`，成交量单位 `{args.left_volume_unit}`，{len(left)} 行，{summary['left']['first_date']} 至 {summary['left']['last_date']}
- 右侧：{args.right_label}，复权 `{args.right_adjustment}`，成交量单位 `{args.right_volume_unit}`，{len(right)} 行，{summary['right']['first_date']} 至 {summary['right']['last_date']}
- 两边都应在抓取时明确选择相同复权口径；本报告只比较文件结果，不独立证明接口参数含义。

## 核验结果

| 项目 | 结果 |
|---|---:|
| 重合交易日 | {len(overlap)} |
| 仅左侧存在 | {only_left} |
| 仅右侧存在 | {only_right} |
| OHLC 全部匹配 | {exact_price_rows}/{len(overlap)} |
| OHLC 最大绝对差 | {max_price_diff:.12g} |
| 最后一个价格不完全匹配的交易日 | {summary['price_comparison']['last_mismatch_date']} |
| 收盘日收益率相关系数 | {summary['close_return_comparison']['correlation']:.12g} |
| 收盘日收益率绝对差中位数 | {summary['close_return_comparison']['median_absolute_difference']:.12g} |
| 收盘日收益率绝对差最大值 | {summary['close_return_comparison']['maximum_absolute_difference']:.12g} |
| 成交量“右 ÷ 左”中位数 | {observed_factor:.12g} |
| 按中位倍率缩放后的成交量相对差中位数 | {summary['volume_comparison']['scaled_by_median_ratio_relative_diff_median']:.12g} |
| 按中位倍率缩放后的成交量相对差最大值 | {summary['volume_comparison']['scaled_by_median_ratio_relative_diff_max']:.12g} |

## 解释边界

- 日期与价格的一致性可以用本次文件直接验证。
- 稳定的成交量倍率说明两个来源的数值单位尺度不同，但仍需结合来源文档，才能把单位正式记为“股”或“手”。
- 本次结果仅验证这只股票和这个日期区间，不能证明任一免费接口未来始终稳定。
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved comparison CSV: {comparison_path}")
    print(f"Saved summary JSON: {json_path}")
    print(f"Saved report Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
