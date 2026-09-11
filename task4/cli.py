from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from urllib.parse import urlparse

from experiments.t4_local.engine import LocalSimulator, SimulatorConfig
from .client import HTTPClient, InProcessClient
from experiments.t4_local.benchmark import run_batch
from .strategies import STRATEGIES, make_strategy


REMOTE_CONFIRMATION = "I_UNDERSTAND_THIS_USES_AN_OFFICIAL_TEST"


def _config(args) -> dict:
    config = {"grid_spacing": args.grid_spacing, "grid_half_extent": args.grid_half_extent}
    if args.strategy in {"lattice", "opportunistic", "belief", "route_optimized", "local_eig", "rejoin_clear", "early_stop", "integrated_route", "clear_probe"}:
        config["lattice_spacing"] = args.lattice_spacing
    if args.strategy in {"opportunistic", "belief", "route_optimized", "local_eig", "rejoin_clear", "early_stop"}:
        config["clear_detour_threshold_m"] = args.clear_detour_threshold
    if args.strategy in {"belief", "local_eig"}:
        config.update(
            particle_count=args.particle_count,
            belief_seed=args.belief_seed,
            assumed_directional_probability=args.assumed_directional_probability,
            belief_travel_weight=args.belief_travel_weight,
        )
    if args.strategy == "local_eig":
        config["eig_distance_slack_m"] = args.eig_distance_slack
    if args.strategy == "early_stop":
        config.update(
            minimum_search_fraction=args.minimum_search_fraction,
            discovery_patience=args.discovery_patience,
            minimum_known_sources=args.minimum_known_sources,
        )
    if args.strategy == "clear_probe":
        config["replacement_distance_m"] = args.replacement_distance
        config["max_replaced_waypoints"] = args.max_replaced_waypoints
    return config


def _add_advanced_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lattice-spacing", type=float, default=735.0)
    parser.add_argument("--clear-detour-threshold", type=float, default=1500.0)
    parser.add_argument("--particle-count", type=int, default=1600)
    parser.add_argument("--belief-seed", type=int, default=20260911)
    parser.add_argument("--assumed-directional-probability", type=float, default=0.5)
    parser.add_argument("--belief-travel-weight", type=float, default=16.0)
    parser.add_argument("--eig-distance-slack", type=float, default=250.0)
    parser.add_argument("--minimum-search-fraction", type=float, default=0.75)
    parser.add_argument("--discovery-patience", type=int, default=7)
    parser.add_argument("--minimum-known-sources", type=int, default=10)
    parser.add_argument("--replacement-distance", type=float, default=400.0)
    parser.add_argument("--max-replaced-waypoints", type=int, default=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="CUMCM B T4 robot and experiment CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one local or official case")
    run.add_argument("--mode", choices=("local", "remote"), required=True)
    run.add_argument("--strategy", choices=sorted(STRATEGIES), default="clear_probe")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--server")
    run.add_argument("--robot-id", default="local-robot")
    run.add_argument("--confirm-remote")
    run.add_argument("--output", type=Path)
    run.add_argument("--grid-spacing", type=float, default=600.0)
    run.add_argument("--grid-half-extent", type=float, default=1800.0)
    _add_advanced_strategy_arguments(run)

    batch = sub.add_parser("batch", help="repeatable in-process local benchmark")
    batch.add_argument("--strategy", choices=sorted(STRATEGIES), required=True)
    batch.add_argument("--seed-start", type=int, default=0)
    batch.add_argument("--cases", type=int, default=100)
    batch.add_argument("--output-dir", type=Path, required=True)
    batch.add_argument("--grid-spacing", type=float, default=600.0)
    batch.add_argument("--grid-half-extent", type=float, default=1800.0)
    batch.add_argument("--directional-probability", type=float, default=0.5)
    _add_advanced_strategy_arguments(batch)

    check = sub.add_parser("config-check", help="validate remote settings without sending HTTP")
    check.add_argument("--server", required=True)
    check.add_argument("--robot-id", required=True)

    args = parser.parse_args()
    if args.command == "config-check":
        parsed = urlparse(args.server)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            parser.error("--server must be an absolute http(s) URL")
        if not args.robot_id.strip() or args.robot_id == "local-robot":
            parser.error("set the actual competition robot/team id")
        print(json.dumps({"valid": True, "server": args.server.rstrip("/"), "robot_id": args.robot_id, "network_actions": 0}, ensure_ascii=False, indent=2))
        return
    if args.command == "batch":
        seeds = list(range(args.seed_start, args.seed_start + args.cases))
        simulator_config = {"directional_probability": args.directional_probability}
        print(json.dumps(run_batch(args.strategy, seeds, args.output_dir, _config(args), simulator_config), ensure_ascii=False, indent=2))
        return

    if args.mode == "remote":
        if not args.server:
            parser.error("remote mode requires --server")
        if not args.output:
            parser.error("remote mode requires --output so the complete action log is preserved")
        if args.confirm_remote != REMOTE_CONFIRMATION:
            parser.error(f"remote mode requires --confirm-remote {REMOTE_CONFIRMATION}")
        client = HTTPClient(args.server, args.robot_id)
        simulator = None
    elif args.server:
        simulator = None
        client = HTTPClient(args.server, args.robot_id)
    else:
        simulator = LocalSimulator(SimulatorConfig(seed=args.seed, robot_id=args.robot_id))
        client = InProcessClient(simulator, args.robot_id)
    result = make_strategy(args.strategy, **_config(args)).run(client)
    payload = {"strategy_result": asdict(result), "actions": client.actions}
    if simulator is not None:
        payload["local_truth"] = simulator.truth_summary()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    concise = {"strategy_result": asdict(result), "action_log_count": len(client.actions)}
    if simulator is not None:
        concise["local_truth_summary"] = {k: v for k, v in simulator.truth_summary().items() if k != "emitters"}
    print(json.dumps(concise, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
