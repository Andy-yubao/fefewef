"""Guarded launcher for problem-3 practice runs; it has no formal-test mode."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from task3.src.main import main as controller_main
from task3.src.policies import POLICIES


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--robot-id", required=True)
    p.add_argument("--base-url", default="http://127.0.0.1:2026")
    p.add_argument("--case-id", required=True, help="practice case code shown by the simulator")
    p.add_argument("--known-total", type=int)
    p.add_argument("--output-dir", type=Path, default=Path("task3/results/raw/practice"))
    p.add_argument("--policy", choices=sorted(POLICIES),
                   help="registered policy ID; overrides --mode and --local-family")
    p.add_argument("--mode", choices=["two_stage", "enroute", "rolling_hard", "hybrid"],
                   default="hybrid")
    p.add_argument("--local-family",
                   choices=["geometry", "e_optimal", "expected_diameter", "shortlist"],
                   default="shortlist")
    p.add_argument("--local-action-limit", type=int,
                   help="override the registered policy; defaults to 3 without --policy")
    args = p.parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{args.case_id}-{stamp}"
    summary = args.output_dir / f"{stem}.summary.json"
    code = 2
    try:
        strategy_args = (
            ["--policy", args.policy] if args.policy else
            ["--mode", args.mode, "--local-family", args.local_family]
        )
        code = controller_main([
            "--robot-id", args.robot_id, "--base-url", args.base_url,
            *strategy_args,
            *(["--local-action-limit", str(args.local_action_limit)]
              if args.local_action_limit is not None else []),
            "--log", str(args.output_dir / f"{stem}.jsonl"),
            "--summary", str(summary),
            *(["--known-total", str(args.known_total)] if args.known_total is not None else []),
        ])
    finally:
        if summary.exists():
            data = json.loads(summary.read_text(encoding="utf-8"))
            data["case_id"] = args.case_id
            data["test_module"] = "problem3_practice"
            if args.policy:
                spec = POLICIES[args.policy]
                data["strategy"] = {
                    "policy_id": args.policy,
                    "mode": spec.mode,
                    "local_family": spec.local_family,
                    "planner_overrides": spec.planner_overrides,
                }
            else:
                data["strategy"] = {
                    "policy_id": None,
                    "mode": args.mode,
                    "local_family": args.local_family,
                    "local_action_limit": 3 if args.local_action_limit is None else args.local_action_limit,
                }
            summary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
