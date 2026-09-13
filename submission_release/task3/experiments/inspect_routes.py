"""Print route diagnostics from action-preserving offline result files."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--policy")
    parser.add_argument("--first", type=int)
    args = parser.parse_args()
    opener = gzip.open if args.input.suffix == ".gz" else open
    with opener(args.input, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    selected = [row for row in rows if row.get("record_type") != "metadata"]
    if args.policy:
        selected = [row for row in selected if row["policy"] == args.policy]
    selected.sort(key=lambda row: row["scenario_seed"])
    if args.first is not None:
        selected = selected[:args.first]
    values = np.asarray([row["result"]["virtual_time_s"] for row in selected], float)
    if len(values):
        print(json.dumps({
            "summary": True, "n": len(values), "mean_s": float(np.mean(values)),
            "median_s": float(np.median(values)), "max_s": float(np.max(values)),
        }, sort_keys=True))
    for row in selected:
        actions = row.get("actions", [])
        moving = [action for action in actions if action.get("movement_s", 0.0) > 0.0]
        longest = sorted(moving, key=lambda action: action["movement_s"], reverse=True)[:10]
        result = row["result"]
        decisions = [d for d in result["diagnostics"] if d.get("type") == "decision"]
        counts: dict[str, int] = {}
        for decision in decisions:
            key = f"{decision['kind']}:{decision['source']}"
            counts[key] = counts.get(key, 0) + 1
        print(json.dumps({
            "scenario_id": row["scenario_id"],
            "policy": row["policy"],
            "virtual_time_s": result["virtual_time_s"],
            "movement_s": result["time_breakdown"]["movement_s"],
            "coverage_completed": result["coverage_completed"],
            "decision_counts": counts,
            "longest_moves": [
                {
                    "path": action["path"],
                    "channel": action.get("channel"),
                    "position": action.get("position"),
                    "movement_s": action["movement_s"],
                }
                for action in longest
            ],
        }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
