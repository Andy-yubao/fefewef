"""Export the seven-point coordinates and analytic coverage certificate."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from task3.src.coverage import analytic_certificate


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=Path("task3/results/tables"))
    args = p.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cert = analytic_certificate()
    with (args.output_dir / "coverage_points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["coverage_index", "x_m", "y_m"])
        for i, point in enumerate(cert.centers): writer.writerow([i, float(point[0]), float(point[1])])
    row = {
        "inner_voronoi_m": cert.inner_voronoi_m,
        "boundary_midpoint_m": cert.boundary_midpoint_m,
        "worst_distance_m": cert.worst_distance_m,
        "minimum_margin_m": cert.margin_m,
        "route_length_m": cert.route_length_m,
        "valid": cert.valid,
    }
    with (args.output_dir / "coverage_certificate.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    print(args.output_dir / "coverage_certificate.csv")


if __name__ == "__main__":
    main()

