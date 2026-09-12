"""CLI entry point for a practice simulator run (never starts formal tests)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import subprocess

from .client import SimulatorClient
from .config import ClientConfig, PhysicalConfig, PlannerConfig, config_dict
from .controller import SearchController
from .policies import POLICIES
from .task_driven_controller import TaskDrivenController
from .dynamic_open_route_controller import DynamicOpenRouteController
from .scheduler import Scheduler


def repository_version() -> dict[str, str | bool]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True,
                                capture_output=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], check=True, text=True,
                                    capture_output=True).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except Exception:
        return {"commit": "unavailable", "dirty": True}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:2026")
    p.add_argument("--robot-id", required=True, help="current simulator login/team id; never stored in source")
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--policy", choices=sorted(POLICIES),
                   help="registered policy ID; overrides --mode and --local-family")
    p.add_argument("--mode", choices=["two_stage", "enroute", "rolling_hard", "hybrid"],
                   default="hybrid")
    p.add_argument("--local-family", choices=sorted(Scheduler.FAMILIES),
                   default="shortlist")
    p.add_argument("--local-action-limit", type=int,
                   help="override the policy value; defaults to 3 without --policy")
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--known-total", type=int, help="practice truth shown by UI, if known")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client_cfg = ClientConfig(args.base_url, "default", args.robot_id, args.timeout, args.retries)
    if args.policy:
        spec = POLICIES[args.policy]
        planner_values = {**spec.planner_overrides, "seed": args.seed}
        if args.local_action_limit is not None:
            planner_values["local_action_limit"] = args.local_action_limit
        mode, local_family = spec.mode, spec.local_family
        controller_kind = spec.controller
    else:
        planner_values = {
            "local_action_limit": 3 if args.local_action_limit is None else args.local_action_limit,
            "seed": args.seed,
        }
        mode, local_family = args.mode, args.local_family
        controller_kind = "legacy"
    planner = PlannerConfig(**planner_values)
    strategy = {
        "policy_id": args.policy,
        "mode": mode,
        "local_family": local_family,
        "controller": controller_kind,
        "planner_overrides": planner_values,
    }
    client = SimulatorClient(client_cfg, args.log)
    if controller_kind == "task_queue":
        controller = TaskDrivenController(
            client, PhysicalConfig(), planner, args.known_total
        )
    elif controller_kind == "dynamic_open_route":
        controller = DynamicOpenRouteController(
            client, PhysicalConfig(), planner, args.known_total
        )
    else:
        controller = SearchController(
            client, mode, local_family, PhysicalConfig(), planner, args.known_total
        )
    try:
        result = controller.run()
    except Exception as exc:
        exit_error = None
        if client._entered_monotonic is not None:
            try:
                client.exit()  # abnormal but safe exit; never reported as a valid completion
            except Exception as stop_exc:
                exit_error = repr(stop_exc)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        error_output = {"success": False, "error": repr(exc),
                        "safe_exit_error": exit_error,
                        "last_valid_virtual_time_s": client.last_virtual_time_s,
                        "repository": repository_version(),
                        "configuration": config_dict(client_cfg, PhysicalConfig(), planner),
                        "strategy": strategy}
        error_output["configuration"]["ClientConfig"]["robot_id"] = "<redacted>"
        args.summary.write_text(json.dumps(error_output, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        raise
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    output = {**result.to_dict(), "repository": repository_version(),
              "configuration": config_dict(client_cfg, PhysicalConfig(), planner),
              "strategy": strategy}
    # Avoid persisting the team identifier; raw request logs redact it too.
    output["configuration"]["ClientConfig"]["robot_id"] = "<redacted>"
    args.summary.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.success else 2


if __name__ == "__main__":
    sys.exit(main())
