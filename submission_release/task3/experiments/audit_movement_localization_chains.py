"""Audit movement and per-source localization chains from saved Q3 runs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np


POLICY = "candidate_020_grid5_center_approach"
EXPECTED_SEEDS = list(range(321100, 321110))
SPEED_MPS = 5.0


def load_records(path: Path, policy: str) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    return sorted(
        (record for record in records if record.get("policy") == policy),
        key=lambda record: int(record["scenario_seed"]),
    )


def decisions(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in record["result"]["diagnostics"]
        if item.get("type") == "decision"
    ]


def moving_actions(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [action for action in record["actions"] if action.get("movement_s", 0.0) > 1e-12]


def validate_and_pair(record: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    selected = decisions(record)
    moved = moving_actions(record)
    if len(selected) != len(moved):
        raise ValueError(
            f"seed {record['scenario_seed']}: {len(selected)} decisions but "
            f"{len(moved)} moving actions"
        )
    for index, (decision, action) in enumerate(zip(selected, moved), start=1):
        if not np.allclose(decision["position"], action["position"], atol=1e-9):
            raise ValueError(
                f"seed {record['scenario_seed']}: decision/action position mismatch "
                f"at decision {index}"
            )
    paired = list(zip(selected, moved))
    reconstructed = sum(action["movement_s"] for _, action in paired)
    original = float(record["result"]["time_breakdown"]["movement_s"])
    if not np.isclose(reconstructed, original, rtol=0.0, atol=1e-8):
        raise ValueError(
            f"seed {record['scenario_seed']}: reconstructed movement {reconstructed} "
            f"does not match original {original}"
        )
    return paired


def summarize(values: list[float]) -> dict[str, float]:
    return {"mean": mean(values), "median": median(values), "max": max(values)}


def audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    seeds = [int(record["scenario_seed"]) for record in records]
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"expected seeds {EXPECTED_SEEDS}, found {seeds}")

    case_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    center_rows: defaultdict[str, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "movement_time_s": 0.0, "movement_distance_m": 0.0}
    )
    post_discovery_rows: list[dict[str, Any]] = []

    for record in records:
        seed = int(record["scenario_seed"])
        paired = validate_and_pair(record)
        by_kind: dict[str, list[float]] = {
            kind: [
                float(action["movement_s"])
                for decision, action in paired
                if decision["kind"] == kind
            ]
            for kind in ("SEARCH", "LOCALIZE", "CLEAR")
        }
        movement_s = {kind: sum(values) for kind, values in by_kind.items()}
        total_s = sum(movement_s.values())
        original_s = float(record["result"]["time_breakdown"]["movement_s"])
        if not np.isclose(total_s, original_s, rtol=0.0, atol=1e-8):
            raise ValueError(f"seed {seed}: kind decomposition does not conserve movement")
        case_rows.append({
            "seed": seed,
            **{f"{kind.lower()}_movement_time_s": movement_s[kind] for kind in movement_s},
            **{
                f"{kind.lower()}_movement_distance_m": movement_s[kind] * SPEED_MPS
                for kind in movement_s
            },
            "total_movement_time_s": total_s,
            "total_movement_distance_m": total_s * SPEED_MPS,
            "decomposition_error_s": total_s - original_s,
        })

        timing = {
            int(channel): values
            for channel, values in record["result"]["per_channel_timing"].items()
        }
        channels = sorted(int(source["channel"]) for source in record["sources"])
        if sorted(timing) != channels or len(channels) != 16:
            raise ValueError(f"seed {seed}: source timing coverage is incomplete")

        by_channel: defaultdict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for decision, action in paired:
            if decision.get("channel") is not None:
                by_channel[int(decision["channel"])].append((decision, action))

        for channel in channels:
            chain_actions = by_channel[channel]
            localize = [item for item in chain_actions if item[0]["kind"] == "LOCALIZE"]
            clear = [item for item in chain_actions if item[0]["kind"] == "CLEAR"]
            localize_s = sum(float(action["movement_s"]) for _, action in localize)
            clear_s = sum(float(action["movement_s"]) for _, action in clear)
            source_counts = Counter(str(decision["source"]) for decision, _ in localize)
            source_rows.append({
                "seed": seed,
                "channel": channel,
                "localize_count": len(localize),
                "localize_movement_distance_m": localize_s * SPEED_MPS,
                "localize_movement_time_s": localize_s,
                "clear_action_count": len(clear),
                "clear_movement_distance_m": clear_s * SPEED_MPS,
                "clear_movement_time_s": clear_s,
                "first_found_virtual_time_s": timing[channel]["first_found_virtual_time_s"],
                "cleared_virtual_time_s": timing[channel]["cleared_virtual_time_s"],
                "found_to_clear_s": timing[channel]["found_to_clear_s"],
                "localize_source_types": ";".join(
                    f"{name}:{count}" for name, count in sorted(source_counts.items())
                ),
            })
            for decision, action in localize:
                center = center_rows[str(decision["source"])]
                movement_time_s = float(action["movement_s"])
                center["count"] += 1
                center["movement_time_s"] += movement_time_s
                center["movement_distance_m"] += movement_time_s * SPEED_MPS

        all_discovered_s = max(
            float(values["first_found_virtual_time_s"]) for values in timing.values()
        )
        threshold_action_index = next(
            index
            for index, action in enumerate(record["actions"])
            if np.isclose(
                float(action.get("response", {}).get("virtual_time_s", -1.0)),
                all_discovered_s,
                rtol=0.0,
                atol=1e-8,
            )
        )
        threshold_position = record["actions"][threshold_action_index]["position"]
        threshold_decision_index = max(
            index
            for index, (decision, _) in enumerate(paired)
            if np.allclose(decision["position"], threshold_position, atol=1e-9)
            and record["actions"].index(paired[index][1]) <= threshold_action_index
        )
        post_search = [
            (decision, action)
            for index, (decision, action) in enumerate(paired)
            if index > threshold_decision_index and decision["kind"] == "SEARCH"
        ]
        post_s = sum(float(action["movement_s"]) for _, action in post_search)
        post_discovery_rows.append({
            "seed": seed,
            "all_16_discovered_virtual_time_s": all_discovered_s,
            "post_discovery_search_count": len(post_search),
            "post_discovery_search_movement_time_s": post_s,
            "post_discovery_search_movement_distance_m": post_s * SPEED_MPS,
        })

    aggregate: dict[str, Any] = {}
    total_mean_s = mean(row["total_movement_time_s"] for row in case_rows)
    for kind in ("search", "localize", "clear"):
        times = [row[f"{kind}_movement_time_s"] for row in case_rows]
        distances = [row[f"{kind}_movement_distance_m"] for row in case_rows]
        aggregate[kind] = {
            "movement_time_s": summarize(times),
            "movement_distance_m": summarize(distances),
            "share_of_mean_total": mean(times) / total_mean_s,
        }
    aggregate["total"] = {
        "movement_time_s": summarize([row["total_movement_time_s"] for row in case_rows]),
        "movement_distance_m": summarize([row["total_movement_distance_m"] for row in case_rows]),
    }

    distribution = Counter(
        "4+" if row["localize_count"] >= 4 else str(row["localize_count"])
        for row in source_rows
    )
    total_localize_distance = sum(row["localize_movement_distance_m"] for row in source_rows)
    ranked = sorted(
        source_rows,
        key=lambda row: row["localize_movement_distance_m"],
        reverse=True,
    )
    concentration = {
        "top_10_share": sum(row["localize_movement_distance_m"] for row in ranked[:10])
        / total_localize_distance,
        "four_plus_source_count": sum(row["localize_count"] >= 4 for row in source_rows),
        "four_plus_movement_share": sum(
            row["localize_movement_distance_m"]
            for row in source_rows
            if row["localize_count"] >= 4
        ) / total_localize_distance,
        "zero_localize_source_count": sum(row["localize_count"] == 0 for row in source_rows),
    }
    centers = []
    for source, values in sorted(center_rows.items(), key=lambda item: -item[1]["movement_distance_m"]):
        count = int(values["count"])
        centers.append({
            "source": source,
            **values,
            "average_movement_distance_per_action_m": values["movement_distance_m"] / count,
        })

    return {
        "case_rows": case_rows,
        "source_rows": source_rows,
        "aggregate": aggregate,
        "localize_count_distribution": {key: distribution.get(key, 0) for key in ("0", "1", "2", "3", "4+")},
        "concentration": concentration,
        "top_10": ranked[:10],
        "center_sources": centers,
        "post_discovery_rows": post_discovery_rows,
        "post_discovery_summary": {
            field: summarize([row[field] for row in post_discovery_rows])
            for field in (
                "post_discovery_search_count",
                "post_discovery_search_movement_distance_m",
                "post_discovery_search_movement_time_s",
            )
        },
        "validation": {
            "seed_count": len(records),
            "source_count": len(source_rows),
            "max_abs_decomposition_error_s": max(abs(row["decomposition_error_s"]) for row in case_rows),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--policy", default=POLICY)
    args = parser.parse_args()

    result = audit(load_records(args.input, args.policy))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["source_rows"][0]))
        writer.writeheader()
        writer.writerows(result["source_rows"])
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
