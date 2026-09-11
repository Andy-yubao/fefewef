"""Guarded launcher for problem-3 practice runs; it has no formal-test mode."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from task3.src.main import main as controller_main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--robot-id", required=True)
    p.add_argument("--base-url", default="http://127.0.0.1:2026")
    p.add_argument("--case-id", required=True, help="practice case code shown by the simulator")
    p.add_argument("--known-total", type=int)
    p.add_argument("--output-dir", type=Path, default=Path("task3/results/raw/practice"))
    p.add_argument("--local-action-limit", type=int, default=3)
    args = p.parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{args.case_id}-{stamp}"
    summary = args.output_dir / f"{stem}.summary.json"
    code = 2
    try:
        code = controller_main([
            "--robot-id", args.robot_id, "--base-url", args.base_url,
            "--mode", "hybrid", "--local-family", "shortlist",
            "--local-action-limit", str(args.local_action_limit),
            "--log", str(args.output_dir / f"{stem}.jsonl"),
            "--summary", str(summary),
            *(["--known-total", str(args.known_total)] if args.known_total is not None else []),
        ])
    finally:
        if summary.exists():
            data = json.loads(summary.read_text(encoding="utf-8"))
            data["case_id"] = args.case_id
            data["test_module"] = "problem3_practice"
            summary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
