"""Compare local benchmark summaries without depending on strategy internals.

This module deliberately lives outside ``task4``.  It consumes only persisted JSON
artifacts, so analysis cannot inspect simulator truth while a strategy is running.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "label",
    "strategy",
    "cases",
    "all_clear_case_rate",
    "mean_virtual_time_s",
    "delta_mean_virtual_vs_baseline_pct",
    "p95_virtual_time_s",
    "max_virtual_time_s",
    "mean_movement_distance_m",
    "mean_measure_count",
    "mean_no_signal_count",
    "mean_no_signal_rate",
    "mean_first_clear_time_s",
    "mean_measurements_before_first_clear",
    "mean_wall_time_s",
    "strategy_config",
]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["source"] = str(path)
    return value


def compare(paths: list[Path], baseline_label: str) -> list[dict[str, Any]]:
    summaries = []
    for path in paths:
        summary = _load(path)
        summary["label"] = path.parent.name
        summaries.append(summary)
    baseline = next((item for item in summaries if item["label"] == baseline_label), None)
    if baseline is None:
        raise ValueError(f"baseline label {baseline_label!r} was not found")
    baseline_mean = float(baseline["mean_virtual_time_s"])
    rows = []
    for item in summaries:
        row = {field: item.get(field) for field in FIELDS}
        row["delta_mean_virtual_vs_baseline_pct"] = (
            (float(item["mean_virtual_time_s"]) / baseline_mean - 1.0) * 100.0
        )
        row["strategy_config"] = json.dumps(item.get("strategy_config", {}), ensure_ascii=False)
        rows.append(row)
    return sorted(rows, key=lambda row: float(row["mean_virtual_time_s"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare persisted T4 benchmark summaries")
    parser.add_argument("summaries", nargs="+", type=Path)
    parser.add_argument("--baseline-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    rows = compare(args.summaries, args.baseline_label)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with (args.output_dir / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    headings = [
        "策略标签", "全清率", "平均总时(s)", "相对基线", "P95(s)",
        "平均测量", "平均无信号", "首次清除(s)", "首次清除前测量",
    ]
    lines = ["# T4 策略对比", "", "| " + " | ".join(headings) + " |", "|" + "---|" * len(headings)]
    for row in rows:
        values = [
            str(row["label"]),
            f'{100 * float(row["all_clear_case_rate"]):.2f}%',
            f'{float(row["mean_virtual_time_s"]):.1f}',
            f'{float(row["delta_mean_virtual_vs_baseline_pct"]):+.2f}%',
            f'{float(row["p95_virtual_time_s"]):.1f}',
            f'{float(row["mean_measure_count"]):.1f}',
            f'{float(row["mean_no_signal_count"]):.1f}',
            f'{float(row["mean_first_clear_time_s"]):.1f}',
            f'{float(row["mean_measurements_before_first_clear"]):.1f}',
        ]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", f"基线标签：`{args.baseline_label}`。所有数字来自输入的本地模拟汇总文件。", ""])
    (args.output_dir / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
