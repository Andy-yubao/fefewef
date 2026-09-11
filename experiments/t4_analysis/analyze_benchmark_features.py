"""Extract descriptive features from persisted T4 benchmark CSV files.

The analysis is post-run and intentionally separate from deployable strategy code.
It may use local truth-assisted columns such as emitter type, but never influences a
robot action.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from typing import Any, Callable


NUMERIC_FIELDS = {
    "seed", "emitter_count", "directional_count", "cleared_count", "clear_rate",
    "average_localize_clear_time_s", "virtual_time_s", "movement_time_s",
    "movement_distance_m", "measure_time_s", "measure_count", "no_signal_count",
    "no_signal_rate", "direction_count", "near_count", "channel_switch_count",
    "optical_count", "clear_attempt_count", "clear_success_count",
    "directional_loss_count", "directional_reacquisition_count",
    "mean_first_seen_time_s", "max_first_seen_time_s", "first_clear_time_s",
    "last_clear_time_s", "measurements_before_first_clear", "wall_time_s",
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in NUMERIC_FIELDS:
            if field in row and row[field] != "":
                row[field] = float(row[field])
        row["all_cleared"] = row.get("all_cleared") == "True"
        row["directional_fraction"] = row["directional_count"] / row["emitter_count"]
    return rows


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def describe(values: list[float]) -> dict[str, float]:
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "mean": mean,
        "sd": sd,
        "cv": sd / mean if mean else 0.0,
        "min": min(values),
        "q25": quantile(values, 0.25),
        "median": quantile(values, 0.5),
        "q75": quantile(values, 0.75),
        "p90": quantile(values, 0.9),
        "p95": quantile(values, 0.95),
        "max": max(values),
    }


def correlation(rows: list[dict[str, Any]], x: str, y: str) -> float:
    pairs = [(float(row[x]), float(row[y])) for row in rows if row.get(x) is not None and row.get(y) is not None]
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((a - mx) * (b - my) for a, b in pairs)
    denominator = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return numerator / denominator if denominator else 0.0


def grouped(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
    buckets: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(key(row), []).append(row)
    result = []
    for name, values in sorted(buckets.items(), key=lambda item: item[0]):
        result.append(
            {
                "group": name,
                "cases": len(values),
                "mean_virtual_time_s": statistics.fmean(r["virtual_time_s"] for r in values),
                "mean_measure_count": statistics.fmean(r["measure_count"] for r in values),
                "mean_no_signal_count": statistics.fmean(r["no_signal_count"] for r in values),
                "mean_no_signal_rate": statistics.fmean(r["no_signal_rate"] for r in values),
                "mean_movement_distance_m": statistics.fmean(r["movement_distance_m"] for r in values),
                "mean_first_clear_time_s": statistics.fmean(r["first_clear_time_s"] for r in values),
            }
        )
    return result


def analyze_primary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [
        "virtual_time_s", "average_localize_clear_time_s", "movement_distance_m",
        "measure_count", "no_signal_count", "no_signal_rate", "first_clear_time_s",
        "max_first_seen_time_s", "directional_loss_count", "wall_time_s",
    ]
    descriptions = {metric: describe([float(row[metric]) for row in rows]) for metric in metrics}
    correlates = [
        "emitter_count", "directional_count", "directional_fraction",
        "movement_distance_m", "measure_count", "no_signal_count", "no_signal_rate",
        "first_clear_time_s", "max_first_seen_time_s", "directional_loss_count",
    ]
    correlations = {field: correlation(rows, field, "virtual_time_s") for field in correlates}
    time_mean = statistics.fmean(row["virtual_time_s"] for row in rows)
    component_means = {
        "movement_time_s": statistics.fmean(row["movement_time_s"] for row in rows),
        "measure_time_s": statistics.fmean(row["measure_time_s"] for row in rows),
        "channel_switch_time_s": statistics.fmean(row["channel_switch_count"] for row in rows),
    }
    component_means["optical_clear_and_rounding_s"] = time_mean - sum(component_means.values())
    component_shares = {key: value / time_mean for key, value in component_means.items()}

    ordered = sorted(rows, key=lambda row: row["virtual_time_s"], reverse=True)
    slowest = [
        {
            key: row[key]
            for key in (
                "seed", "virtual_time_s", "emitter_count", "directional_count",
                "movement_distance_m", "measure_count", "no_signal_count",
                "first_clear_time_s", "max_first_seen_time_s", "directional_loss_count",
            )
        }
        for row in ordered[:10]
    ]
    return {
        "cases": len(rows),
        "all_clear_cases": sum(row["all_cleared"] for row in rows),
        "zero_failure_rule_of_three_upper_95": 3 / len(rows),
        "descriptions": descriptions,
        "correlation_with_virtual_time": correlations,
        "time_component_means": component_means,
        "time_component_shares": component_shares,
        "by_emitter_count": grouped(rows, lambda row: int(row["emitter_count"])),
        "by_directional_fraction": grouped(
            rows,
            lambda row: "low_[0,.33)" if row["directional_fraction"] < 1 / 3 else (
                "mid_[.33,.67)" if row["directional_fraction"] < 2 / 3 else "high_[.67,1]"
            ),
        ),
        "slowest_10": slowest,
    }


def comparison(paths: list[Path]) -> list[dict[str, Any]]:
    result = []
    for path in paths:
        rows = load_cases(path)
        result.append(
            {
                "strategy": rows[0]["strategy"],
                "cases": len(rows),
                "all_clear_rate": sum(row["all_cleared"] for row in rows) / len(rows),
                "mean_virtual_time_s": statistics.fmean(row["virtual_time_s"] for row in rows),
                "p95_virtual_time_s": quantile([row["virtual_time_s"] for row in rows], 0.95),
                "mean_movement_distance_m": statistics.fmean(row["movement_distance_m"] for row in rows),
                "mean_measure_count": statistics.fmean(row["measure_count"] for row in rows),
                "mean_no_signal_count": statistics.fmean(row["no_signal_count"] for row in rows),
                "mean_first_clear_time_s": statistics.fmean(row["first_clear_time_s"] for row in rows),
            }
        )
    return sorted(result, key=lambda row: row["mean_virtual_time_s"])


def random_case_context(primary: list[dict[str, Any]], path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        random_rows = list(csv.DictReader(handle))
    times = sorted(row["virtual_time_s"] for row in primary)
    result = []
    for row in random_rows:
        value = float(row["virtual_time_s"])
        result.append(
            {
                "seed": int(row["seed"]),
                "virtual_time_s": value,
                "empirical_percentile_in_primary": sum(item <= value for item in times) / len(times),
                "emitter_count": int(row["emitter_count"]),
                "directional_count": int(row["directional_count"]),
                "measure_count": int(row["measure_count"]),
                "no_signal_count": int(row["no_signal_count"]),
            }
        )
    return result


def markdown(report: dict[str, Any]) -> str:
    p = report["primary"]
    d = p["descriptions"]
    lines = [
        "# T4 实验数据特征报告",
        "",
        "本报告仅分析已落盘的本地模拟数据；相关性是描述性的，不解释为因果。",
        "",
        "## 主策略总体分布",
        "",
        f'- 案例：{p["cases"]}，全清：{p["all_clear_cases"]}/{p["cases"]}',
        f'- 总时间：均值 {d["virtual_time_s"]["mean"]:.1f} s，标准差 {d["virtual_time_s"]["sd"]:.1f} s，中位数 {d["virtual_time_s"]["median"]:.1f} s，P95 {d["virtual_time_s"]["p95"]:.1f} s，最大 {d["virtual_time_s"]["max"]:.1f} s',
        f'- 移动：均值 {d["movement_distance_m"]["mean"]:.0f} m；测量：{d["measure_count"]["mean"]:.1f} 次；无信号：{d["no_signal_count"]["mean"]:.1f} 次（单案例无信号率均值 {100*d["no_signal_rate"]["mean"]:.2f}%）',
        f'- 首次清除：均值 {d["first_clear_time_s"]["mean"]:.1f} s，中位数 {d["first_clear_time_s"]["median"]:.1f} s，P95 {d["first_clear_time_s"]["p95"]:.1f} s',
        f'- 算法墙钟时间：均值 {1000*d["wall_time_s"]["mean"]:.2f} ms/案例',
        "",
        "## 虚拟时间构成",
        "",
    ]
    for key, value in p["time_component_means"].items():
        lines.append(f'- `{key}`：{value:.1f} s（{100*p["time_component_shares"][key]:.2f}%）')

    emitter_groups = {int(row["group"]): row for row in p["by_emitter_count"]}
    direction_groups = {row["group"]: row for row in p["by_directional_fraction"]}
    low_direction = direction_groups.get("low_[0,.33)")
    high_direction = direction_groups.get("high_[.67,1]")
    lines.extend(
        [
            "",
            "## 主要数据特征解释",
            "",
            f'- 路线是首要成本：移动占总时间 {100*p["time_component_shares"]["movement_time_s"]:.2f}%，且移动距离与总时间相关系数为 {p["correlation_with_virtual_time"]["movement_distance_m"]:+.3f}。',
            f'- 无信号仍是主要动作形态：平均 {d["no_signal_count"]["mean"]:.1f}/{d["measure_count"]["mean"]:.1f} 次测量无信号。结合题目规则推断，未占用频道和定向半平面外观测会持续产生这种成本，不能靠一次负观测安全删除频道。',
            f'- 首次清除呈右偏：中位数 {d["first_clear_time_s"]["median"]:.1f} s，均值 {d["first_clear_time_s"]["mean"]:.1f} s，P95 {d["first_clear_time_s"]["p95"]:.1f} s；少数迟迟无法形成精确交会的案例拉高均值。',
        ]
    )
    if 10 in emitter_groups and 16 in emitter_groups:
        lines.append(
            f'- 源越多，测量反而越少：10 源平均 {emitter_groups[10]["mean_measure_count"]:.1f} 次，16 源平均 {emitter_groups[16]["mean_measure_count"]:.1f} 次。原因包括未占用频道更少；达到题目上限 16 后策略还能立即结束剩余搜索，因此 16 源组总时间出现明显下降。'
        )
    if low_direction and high_direction:
        lines.append(
            f'- 定向源占比升高会增加难度：高定向占比组比低占比组平均多用 {high_direction["mean_virtual_time_s"]-low_direction["mean_virtual_time_s"]:.1f} s、多测 {high_direction["mean_measure_count"]-low_direction["mean_measure_count"]:.1f} 次，首次清除晚 {high_direction["mean_first_clear_time_s"]-low_direction["mean_first_clear_time_s"]:.1f} s。'
        )
    lines.append(
        f'- 总时间分布相对集中，变异系数为 {100*d["virtual_time_s"]["cv"]:.2f}%；不过最慢案例仍比均值高 {(d["virtual_time_s"]["max"]/d["virtual_time_s"]["mean"]-1)*100:.1f}%，尾部主要同时具有长路线、较多测量和较多定向失锁。'
    )

    lines.extend(["", "## 按干扰源总数分组", "", "| 源数 | 案例 | 总时间(s) | 测量 | 无信号 | 无信号率 | 移动(m) | 首次清除(s) |", "|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in p["by_emitter_count"]:
        lines.append(
            f'| {row["group"]} | {row["cases"]} | {row["mean_virtual_time_s"]:.1f} | {row["mean_measure_count"]:.1f} | '
            f'{row["mean_no_signal_count"]:.1f} | {100*row["mean_no_signal_rate"]:.2f}% | {row["mean_movement_distance_m"]:.0f} | {row["mean_first_clear_time_s"]:.1f} |'
        )

    lines.extend(["", "## 按定向源占比分组", "", "| 定向占比 | 案例 | 总时间(s) | 测量 | 无信号 | 移动(m) | 首次清除(s) |", "|---|---:|---:|---:|---:|---:|---:|"])
    for row in p["by_directional_fraction"]:
        lines.append(
            f'| {row["group"]} | {row["cases"]} | {row["mean_virtual_time_s"]:.1f} | {row["mean_measure_count"]:.1f} | '
            f'{row["mean_no_signal_count"]:.1f} | {row["mean_movement_distance_m"]:.0f} | {row["mean_first_clear_time_s"]:.1f} |'
        )

    lines.extend(["", "## 与总时间的 Pearson 相关系数", ""])
    for key, value in sorted(p["correlation_with_virtual_time"].items(), key=lambda item: abs(item[1]), reverse=True):
        lines.append(f'- `{key}`：{value:+.3f}')

    lines.extend(["", "## 策略对比", "", "| 策略 | 全清率 | 平均总时(s) | P95(s) | 移动(m) | 测量 | 无信号 | 首次清除(s) |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for row in report["strategy_comparison"]:
        lines.append(
            f'| {row["strategy"]} | {100*row["all_clear_rate"]:.1f}% | {row["mean_virtual_time_s"]:.1f} | '
            f'{row["p95_virtual_time_s"]:.1f} | {row["mean_movement_distance_m"]:.0f} | {row["mean_measure_count"]:.1f} | '
            f'{row["mean_no_signal_count"]:.1f} | {row["mean_first_clear_time_s"]:.1f} |'
        )

    lines.extend(["", "## 三次可视化随机案例在主基准中的位置", "", "| Seed | 总时间(s) | 经验百分位 | 源数 | 定向源 | 测量 | 无信号 |", "|---:|---:|---:|---:|---:|---:|---:|"])
    for row in report["random_cases"]:
        lines.append(
            f'| {row["seed"]} | {row["virtual_time_s"]:.1f} | {100*row["empirical_percentile_in_primary"]:.1f}% | '
            f'{row["emitter_count"]} | {row["directional_count"]} | {row["measure_count"]} | {row["no_signal_count"]} |'
        )

    lines.extend(["", "## 最慢的 10 个案例", "", "| Seed | 总时间(s) | 源数 | 定向源 | 移动(m) | 测量 | 无信号 | 首次清除(s) | 最晚首见(s) | 失锁 |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in p["slowest_10"]:
        lines.append(
            f'| {int(row["seed"])} | {row["virtual_time_s"]:.1f} | {int(row["emitter_count"])} | {int(row["directional_count"])} | '
            f'{row["movement_distance_m"]:.0f} | {row["measure_count"]:.0f} | {row["no_signal_count"]:.0f} | '
            f'{row["first_clear_time_s"]:.1f} | {row["max_first_seen_time_s"]:.1f} | {row["directional_loss_count"]:.0f} |'
        )
    lines.extend(["", f'零失败的经验结果不等于失败概率为零；按 rule-of-three，{p["cases"]} 次零失败对应的粗略 95% 失败率上界约为 {100*p["zero_failure_rule_of_three_upper_95"]:.2f}%。', ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze persisted T4 benchmark features")
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--compare", nargs="*", type=Path, default=[])
    parser.add_argument("--random-summary", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    primary = load_cases(args.primary)
    report = {
        "primary_source": str(args.primary),
        "primary": analyze_primary(primary),
        "strategy_comparison": comparison(args.compare),
        "random_cases": random_case_context(primary, args.random_summary),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "feature_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "feature_report.md").write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
