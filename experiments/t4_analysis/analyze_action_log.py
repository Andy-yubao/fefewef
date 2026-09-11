from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    actions = payload["actions"]
    measures = [action for action in actions if action["path"] == "/measure"]
    clears = [action for action in actions if action["path"] == "/clear"]
    result_counts = Counter(action["response"]["measure_result"] for action in measures)
    unique_positions = {
        (action["request"]["position"]["x"], action["request"]["position"]["y"])
        for action in measures
    }

    channel_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "measurements": 0,
            "no_signal": 0,
            "direction": 0,
            "near": 0,
            "first_signal_action": None,
            "first_signal_virtual_time_s": None,
            "last_measure_action": None,
        }
    )
    for action_index, action in enumerate(actions, start=1):
        if action["path"] != "/measure":
            continue
        channel = int(action["request"]["channel"])
        result = action["response"]["measure_result"]
        stats = channel_stats[channel]
        stats["measurements"] += 1
        stats[result] += 1
        stats["last_measure_action"] = action_index
        if result != "no_signal" and stats["first_signal_action"] is None:
            stats["first_signal_action"] = action_index
            stats["first_signal_virtual_time_s"] = action["response"]["virtual_time_s"]

    first_clear_index = next(
        (index for index, action in enumerate(actions, start=1) if action["path"] == "/clear"),
        None,
    )
    last_measure_index = max(
        (index for index, action in enumerate(actions, start=1) if action["path"] == "/measure"),
        default=None,
    )
    discovered_channels = sorted(
        channel for channel, stats in channel_stats.items() if stats["first_signal_action"] is not None
    )
    undiscovered_channels = sorted(set(range(1, 21)) - set(discovered_channels))
    no_signal_before_first_detection = sum(
        stats["no_signal"]
        for channel, stats in channel_stats.items()
        if channel in discovered_channels
    )

    return {
        "strategy": payload["strategy_result"]["strategy"],
        "total_actions": len(actions),
        "accepted_actions": sum(action["response"].get("accepted") is True for action in actions),
        "measurements": len(measures),
        "unique_measure_positions": len(unique_positions),
        "measure_result_counts": dict(result_counts),
        "no_signal_rate": result_counts["no_signal"] / len(measures) if measures else None,
        "clear_attempts": len(clears),
        "clear_successes": sum(action["response"].get("clear_result") == "success" for action in clears),
        "first_clear_action": first_clear_index,
        "last_measure_action": last_measure_index,
        "all_clears_after_last_measure": bool(clears) and first_clear_index > last_measure_index,
        "discovered_channels": discovered_channels,
        "undiscovered_channels": undiscovered_channels,
        "no_signal_measurements_on_eventually_discovered_channels": no_signal_before_first_detection,
        "final_virtual_time_s": payload["strategy_result"]["final_virtual_time_s"],
        "channel_stats": {str(channel): channel_stats[channel] for channel in sorted(channel_stats)},
    }


def markdown_report(source: Path, summary: dict[str, Any]) -> str:
    counts = summary["measure_result_counts"]
    rows = []
    for channel, stats in summary["channel_stats"].items():
        rows.append(
            f"| {channel} | {stats['measurements']} | {stats['no_signal']} | "
            f"{stats['direction']} | {stats['near']} | "
            f"{stats['first_signal_virtual_time_s'] if stats['first_signal_virtual_time_s'] is not None else '-'} |"
        )
    return f"""# T4 action-log analysis

- Source: `{source}`
- Strategy: `{summary['strategy']}`
- Actions: {summary['total_actions']} ({summary['accepted_actions']} accepted)
- Measurement positions: {summary['unique_measure_positions']}
- Measurements: {summary['measurements']}
- `no_signal`: {counts.get('no_signal', 0)} ({summary['no_signal_rate']:.2%})
- `direction`: {counts.get('direction', 0)}
- `near`: {counts.get('near', 0)}
- Clears: {summary['clear_successes']}/{summary['clear_attempts']}
- First clear action: {summary['first_clear_action']}
- Last measurement action: {summary['last_measure_action']}
- All clears after the last measurement: {summary['all_clears_after_last_measure']}
- No-signal measurements spent on channels that were eventually discovered: {summary['no_signal_measurements_on_eventually_discovered_channels']}

## Per-channel measurements

| Channel | Measures | No signal | Direction | Near | First signal virtual time (s) |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Interpretation boundary

This report uses only robot-visible request/response logs. It does not infer the hidden true emitter count, source positions, radii, types, or directions.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a saved T4 action log without importing robot code")
    parser.add_argument("log", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.log.read_text(encoding="utf-8"))
    summary = analyze(payload)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.log.stem
    (args.output_dir / f"{stem}-analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / f"{stem}-analysis.md").write_text(
        markdown_report(args.log, summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
