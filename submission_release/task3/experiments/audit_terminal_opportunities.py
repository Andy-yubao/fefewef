"""Audit route-compatible terminal opportunities in candidate-020 decisions."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Any


POLICY = "candidate_020_grid5_center_approach"


def load_records(path: Path) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        records = [
            row for row in map(json.loads, handle)
            if row.get("policy") == POLICY
        ]
    records.sort(key=lambda row: row["scenario_seed"])
    seeds = [record["scenario_seed"] for record in records]
    if seeds != list(range(321100, 321110)):
        raise ValueError(f"expected seeds 321100--321109, found {seeds}")
    return records


def opportunity_row(
    record: dict[str, Any],
    decision_index: int,
    audit: dict[str, Any],
    candidate: dict[str, Any],
    opportunity_type: str,
) -> dict[str, Any]:
    channel = int(candidate["channel"])
    snapshot = next(
        item for item in audit["channel_snapshots"]
        if int(item["channel"]) == channel
    )
    current = audit["current_position"]
    action_position = candidate["position"]
    coverage = audit["coverage_next_position"]
    search_score = float(audit["coverage_next_score_s"])
    action_score = float(candidate["score_s"])
    delta_route = float(candidate["route_insertion_delta_m"])
    route_limit = float(record["planner"]["route_insert_limit_m"])
    clear_threshold = 20.0 - float(record["planner"]["clear_margin_m"])
    expected_radius = candidate["candidate_expected_radius_m"]
    return {
        "opportunity_type": opportunity_type,
        "seed": record["scenario_seed"],
        "decision_index": decision_index,
        "channel": channel,
        "current_x_m": current[0],
        "current_y_m": current[1],
        "action_x_m": action_position[0],
        "action_y_m": action_position[1],
        "next_coverage_x_m": coverage[0],
        "next_coverage_y_m": coverage[1],
        "current_certificate_radius_m": snapshot["certificate_radius_m"],
        "candidate_expected_radius_m": expected_radius,
        "clear_threshold_m": clear_threshold,
        "route_insertion_delta_m": delta_route,
        "action_score_s": action_score,
        "search_score_s": search_score,
        "search_minus_action_s": search_score - action_score,
        "chosen_kind": audit["chosen_kind"],
        "chosen_channel": audit["chosen_channel"],
        "chosen_source": audit["chosen_source"],
        "route_compatible": delta_route <= route_limit,
        "search_chosen": audit["chosen_kind"] == "SEARCH",
    }


def extract(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        clear_threshold = 20.0 - float(record["planner"]["clear_margin_m"])
        audits = [
            item for item in record["result"]["diagnostics"]
            if item.get("type") == "scheduler_audit"
        ]
        for decision_index, audit in enumerate(audits, start=1):
            if audit["coverage_next_score_s"] is None:
                continue
            for candidate in audit["local_candidates"]:
                if candidate["kind"] == "CLEAR":
                    rows.append(opportunity_row(
                        record, decision_index, audit, candidate, "CLEAR"
                    ))
                elif (
                    candidate["kind"] == "LOCALIZE"
                    and candidate["candidate_expected_radius_m"] <= clear_threshold
                ):
                    rows.append(opportunity_row(
                        record, decision_index, audit, candidate,
                        "EXPECTED_CLEARABLE_LOCALIZE",
                    ))
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for opportunity_type in ("CLEAR", "EXPECTED_CLEARABLE_LOCALIZE"):
        selected = [row for row in rows if row["opportunity_type"] == opportunity_type]
        compatible = [row for row in selected if row["route_compatible"]]
        missed = [row for row in compatible if row["search_chosen"]]
        summary[opportunity_type] = {
            "total": len(selected),
            "decision_count": len({(row["seed"], row["decision_index"]) for row in selected}),
            "route_compatible": len(compatible),
            "route_compatible_search_chosen": len(missed),
            "missed_seed_count": len({row["seed"] for row in missed}),
            "missed_channel_count": len({row["channel"] for row in missed}),
            "missed_seeds": sorted({row["seed"] for row in missed}),
            "missed_channels": sorted({row["channel"] for row in missed}),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = extract(load_records(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
