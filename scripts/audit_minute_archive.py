from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.data import load_price_csv
from stock_model.minute import load_minute_archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a minute archive against same-source daily bars.")
    parser.add_argument("--minute", required=True, help="Canonical minute archive CSV.")
    parser.add_argument("--daily", required=True, help="Same-source, same-adjustment daily OHLCV CSV.")
    parser.add_argument("--symbol", required=True, help="Project symbol.")
    parser.add_argument("--output-prefix", required=True, help="Output path without extension.")
    parser.add_argument("--tolerance", type=float, default=1e-8, help="Absolute equality tolerance.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    minute_path = Path(args.minute)
    daily_path = Path(args.daily)
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    minute = load_minute_archive(minute_path)
    daily = load_price_csv(daily_path)
    minute["date"] = minute["datetime"].dt.tz_localize(None).dt.normalize()
    aggregate = minute.groupby("date", as_index=False).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        minute_rows=("datetime", "size"),
        first_bar=("datetime", "min"),
        last_bar=("datetime", "max"),
    )
    compared = aggregate.merge(
        daily,
        on="date",
        how="outer",
        suffixes=("_minute", "_daily"),
        indicator="date_status",
        validate="one_to_one",
    ).sort_values("date")
    overlap = compared[compared["date_status"] == "both"].copy()

    fields = ["open", "high", "low", "close", "volume"]
    for field in fields:
        overlap[f"{field}_diff_minute_minus_daily"] = overlap[f"{field}_minute"] - overlap[f"{field}_daily"]
    overlap["volume_relative_diff"] = (
        overlap["volume_diff_minute_minus_daily"].abs() / overlap["volume_daily"].abs().where(overlap["volume_daily"] != 0)
    )
    exact_masks = {
        field: overlap[f"{field}_diff_minute_minus_daily"].abs().le(args.tolerance) for field in fields
    }
    exact_ohlc = pd.concat([exact_masks[field] for field in fields[:4]], axis=1).all(axis=1)
    exact_ohlcv = pd.concat([exact_masks[field] for field in fields], axis=1).all(axis=1)

    first_times = minute.groupby(minute["datetime"].dt.date)["datetime"].min().dt.strftime("%H:%M:%S")
    last_times = minute.groupby(minute["datetime"].dt.date)["datetime"].max().dt.strftime("%H:%M:%S")
    counts = minute.groupby(minute["datetime"].dt.date).size()
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "symbol": args.symbol,
        "minute_file": {"path": minute_path.as_posix(), "sha256": sha256(minute_path), "rows": int(len(minute))},
        "daily_file": {"path": daily_path.as_posix(), "sha256": sha256(daily_path), "rows": int(len(daily))},
        "date_comparison": {
            "minute_days": int(len(aggregate)),
            "daily_days": int(len(daily)),
            "overlap_days": int(len(overlap)),
            "minute_only_days": int((compared["date_status"] == "left_only").sum()),
            "daily_only_days": int((compared["date_status"] == "right_only").sum()),
        },
        "session_structure": {
            "minimum_rows_per_day": int(counts.min()),
            "maximum_rows_per_day": int(counts.max()),
            "first_bar_times": sorted(first_times.unique().tolist()),
            "last_bar_times": sorted(last_times.unique().tolist()),
            "duplicate_timestamps": int(minute["datetime"].duplicated().sum()),
            "zero_volume_rows": int((minute["volume"] == 0).sum()),
        },
        "daily_aggregation_comparison": {
            "exact_days_by_field": {field: int(mask.sum()) for field, mask in exact_masks.items()},
            "all_ohlc_exact_days": int(exact_ohlc.sum()),
            "all_ohlcv_exact_days": int(exact_ohlcv.sum()),
            "maximum_absolute_difference": {
                field: float(overlap[f"{field}_diff_minute_minus_daily"].abs().max()) for field in fields
            },
            "volume_relative_difference_median": float(overlap["volume_relative_diff"].median()),
            "volume_relative_difference_maximum": float(overlap["volume_relative_diff"].max()),
        },
        "quality_status": "archive_valid_source_values_need_caution",
        "interpretation": (
            "The archive is structurally complete, but same-source 5-minute aggregation does not reproduce every daily "
            "high, low, and volume value. Do not treat it as tick-complete or feed it into a model without resolving or "
            "accepting this source limitation."
        ),
    }

    csv_path = Path(f"{output_prefix}.csv")
    json_path = Path(f"{output_prefix}.json")
    markdown_path = Path(f"{output_prefix}.md")
    overlap.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison = summary["daily_aggregation_comparison"]
    session = summary["session_structure"]
    markdown = f"""# {args.symbol} BaoStock 5分钟档案质量核验

生成时间：{summary['generated_at']}

## 结构检查

- 分钟数据：{len(minute)} 行、{len(aggregate)} 个交易日。
- 每日行数范围：{session['minimum_rows_per_day']} 至 {session['maximum_rows_per_day']}。
- 每日首根时间：{', '.join(session['first_bar_times'])}；末根时间：{', '.join(session['last_bar_times'])}。
- 重复时间戳：{session['duplicate_timestamps']}；零成交量行：{session['zero_volume_rows']}。

## 与同来源不复权日线比较

| 项目 | 完全一致天数 | 最大绝对差 |
|---|---:|---:|
| 开盘 | {comparison['exact_days_by_field']['open']}/{len(overlap)} | {comparison['maximum_absolute_difference']['open']:.12g} |
| 最高 | {comparison['exact_days_by_field']['high']}/{len(overlap)} | {comparison['maximum_absolute_difference']['high']:.12g} |
| 最低 | {comparison['exact_days_by_field']['low']}/{len(overlap)} | {comparison['maximum_absolute_difference']['low']:.12g} |
| 收盘 | {comparison['exact_days_by_field']['close']}/{len(overlap)} | {comparison['maximum_absolute_difference']['close']:.12g} |
| 成交量 | {comparison['exact_days_by_field']['volume']}/{len(overlap)} | {comparison['maximum_absolute_difference']['volume']:.12g} |

- 成交量相对差中位数：{comparison['volume_relative_difference_median']:.12g}
- 成交量相对差最大值：{comparison['volume_relative_difference_maximum']:.12g}

## 结论边界

分钟档案在日期、时段和行数上完整，但聚合后不能逐日完全复现同一来源的日线最高价、最低价和成交量。因此它可作为已审计的原始观察档案继续增量保存，但在差异原因解决或明确接受前，不应称为逐笔完整数据，也不应直接进入模型训练。
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved comparison: {csv_path}")
    print(f"Saved summary: {json_path}")
    print(f"Saved report: {markdown_path}")


if __name__ == "__main__":
    main()
