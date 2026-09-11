"""Run paired problem-3 offline experiments and save compressed raw records."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess

from task3.src.config import PhysicalConfig, PlannerConfig, config_dict
from task3.src.controller import SearchController
from task3.src.mock_simulator import MockSimulator, random_scenario


POLICIES = {
    "B0_two_stage": ("two_stage", "shortlist", 3),
    "B1_enroute": ("enroute", "shortlist", 3),
    "B2_rolling_hard": ("rolling_hard", "shortlist", 3),
    "B3_hybrid": ("hybrid", "shortlist", 3),
    "A_geometry": ("hybrid", "geometry", 3),
    "A_e_optimal": ("hybrid", "e_optimal", 3),
    "A_expected_diameter": ("hybrid", "expected_diameter", 3),
    "S_local_limit_1": ("hybrid", "shortlist", 1),
    "S_local_limit_5": ("hybrid", "shortlist", 5),
}


def repository_version() -> dict[str, str | bool]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True,
                                capture_output=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], check=True, text=True,
                                    capture_output=True).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except Exception:
        return {"commit": "unavailable", "dirty": True}


def run_case(args: tuple[int, int, float, bool]) -> list[dict]:
    seed, planner_seed, grid_step, save_actions = args
    physical = PhysicalConfig()
    scenario = random_scenario(seed, physical)
    rows: list[dict] = []
    for policy, (mode, family, limit) in POLICIES.items():
        planner = PlannerConfig(seed=planner_seed, grid_step_m=grid_step, local_action_limit=limit)
        mock = MockSimulator(scenario, physical)
        result = SearchController(mock, mode, family, physical, planner, scenario.total).run()
        row = {
            "scenario_id": scenario.scenario_id,
            "scenario_seed": seed,
            "policy": policy,
            "mode": mode,
            "local_family": family,
            "local_action_limit": limit,
            "source_count": scenario.total,
            "sources": [asdict(s) for s in scenario.sources],
            "result": result.to_dict(),
        }
        if save_actions:
            row["actions"] = mock.actions
        rows.append(row)
    return rows


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", type=int, default=100)
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--grid-step", type=float, default=20.0)
    p.add_argument("--output", type=Path, default=Path("task3/results/raw/offline_runs.jsonl.gz"))
    p.add_argument("--no-actions", action="store_true", help="omit action sequences for quick diagnostics")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.cases <= 0 or args.workers <= 0:
        raise SystemExit("cases and workers must be positive")
    if args.grid_step / 2**0.5 > PhysicalConfig().clear_radius_m:
        raise SystemExit("grid cells are too large for the guaranteed fallback cover")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "record_type": "metadata",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": args.cases,
        "paired_scenario_seed_start": args.seed,
        "policies": POLICIES,
        "configuration": config_dict(PhysicalConfig(), PlannerConfig(seed=args.seed, grid_step_m=args.grid_step)),
        "repository": repository_version(),
        "error_model": "SHA256 location-fixed bounded error; independent locations differ deterministically",
    }
    tasks = [(args.seed + i, args.seed, args.grid_step, not args.no_actions) for i in range(args.cases)]
    with gzip.open(args.output, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\n")
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_case, task): task[0] for task in tasks}
            completed = 0
            for future in as_completed(futures):
                for row in future.result():
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                completed += 1
                print(f"completed {completed}/{args.cases}: seed={futures[future]}", flush=True)
    print(args.output)


if __name__ == "__main__":
    main()
