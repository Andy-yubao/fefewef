"""Plot the distance-to-nearest-center field and its boundary profile."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from coverage_geometry import (
    GUARANTEED_RECEPTION_RADIUS_M,
    TARGET_RADIUS_M,
    analytic_coverage_bound,
    coverage_centers,
    dense_polar_verification,
    nearest_center_distance,
    worst_boundary_points,
)


def make_figure(output: Path, grid_step_m: float = 5.0) -> None:
    values = np.arange(-TARGET_RADIUS_M, TARGET_RADIUS_M + grid_step_m, grid_step_m)
    xx, yy = np.meshgrid(values, values)
    inside = xx**2 + yy**2 <= TARGET_RADIUS_M**2
    distance = nearest_center_distance(xx, yy)
    masked_distance = np.ma.masked_where(~inside, distance)

    angles_deg = np.linspace(0.0, 360.0, 3601)
    angles_rad = np.deg2rad(angles_deg)
    bx = TARGET_RADIUS_M * np.cos(angles_rad)
    by = TARGET_RADIUS_M * np.sin(angles_rad)
    boundary_distance = nearest_center_distance(bx, by)

    bound = analytic_coverage_bound()
    sampled = dense_polar_verification()
    centers = coverage_centers()
    worst = worst_boundary_points()

    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(14, 6.3),
        gridspec_kw={"width_ratios": [1.05, 1.0]},
        constrained_layout=True,
    )

    image = ax0.imshow(
        masked_distance,
        origin="lower",
        extent=[-TARGET_RADIUS_M, TARGET_RADIUS_M] * 2,
        cmap="viridis",
        vmin=0,
        vmax=GUARANTEED_RECEPTION_RADIUS_M,
        interpolation="nearest",
    )
    ax0.contour(
        xx,
        yy,
        distance,
        levels=[600, 800, 900, 950],
        colors="white",
        linewidths=0.7,
    )
    ax0.add_patch(
        plt.Circle((0, 0), TARGET_RADIUS_M, fill=False, color="black", linewidth=1.8)
    )
    ax0.scatter(centers[:, 0], centers[:, 1], c="white", edgecolors="black", s=45)
    ax0.scatter(worst[:, 0], worst[:, 1], c="#ef4444", marker="D", s=34)
    ax0.set_aspect("equal", adjustable="box")
    ax0.set_xlabel("x / m")
    ax0.set_ylabel("y / m")
    ax0.set_title("Distance to nearest coverage point")
    colorbar = fig.colorbar(image, ax=ax0, shrink=0.88)
    colorbar.set_label("nearest-center distance / m")

    ax1.plot(angles_deg, boundary_distance, color="#2563eb", linewidth=2)
    ax1.axhline(
        GUARANTEED_RECEPTION_RADIUS_M,
        color="#dc2626",
        linestyle="--",
        linewidth=2,
        label="1000 m guaranteed reception limit",
    )
    ax1.scatter(
        np.arange(30.0, 360.0, 60.0),
        np.full(6, bound["boundary_midpoint_m"]),
        color="#dc2626",
        marker="D",
        s=38,
        zorder=3,
        label="analytic worst positions",
    )
    ax1.set_xlim(0, 360)
    ax1.set_ylim(0, 1050)
    ax1.set_xticks(np.arange(0, 361, 60))
    ax1.set_xlabel("target-boundary polar angle / degree")
    ax1.set_ylabel("nearest-center distance / m")
    ax1.set_title("Worst case occurs between adjacent ring points")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="lower right")
    ax1.text(
        0.02,
        0.98,
        f"Analytic max: {bound['worst_distance_m']:.2f} m\n"
        f"Dense sample: {sampled['sampled_worst_distance_m']:.2f} m\n"
        f"Minimum margin: {bound['minimum_margin_m']:.2f} m\n"
        f"Samples: {sampled['sample_count']:,}",
        transform=ax1.transAxes,
        ha="left",
        va="top",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "alpha": 0.92},
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "seven_point_margin.png",
    )
    parser.add_argument("--grid-step-m", type=float, default=5.0)
    args = parser.parse_args()
    make_figure(args.output, args.grid_step_m)
    print(args.output)


if __name__ == "__main__":
    main()
