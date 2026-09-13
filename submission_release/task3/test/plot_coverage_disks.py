"""Plot the target disk, seven guaranteed-reception disks, and visit route."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from coverage_geometry import (
    GUARANTEED_RECEPTION_RADIUS_M,
    TARGET_RADIUS_M,
    analytic_coverage_bound,
    coverage_centers,
    worst_boundary_points,
)


def make_figure(output: Path) -> None:
    centers = coverage_centers()
    worst = worst_boundary_points()
    bound = analytic_coverage_bound()

    fig, ax = plt.subplots(figsize=(9, 9), constrained_layout=True)
    ax.add_patch(
        Circle(
            (0, 0),
            TARGET_RADIUS_M,
            facecolor="#f3f4f6",
            edgecolor="#111827",
            linewidth=2.4,
            label="Target disk (R = 1800 m)",
            zorder=0,
        )
    )

    colors = ["#2563eb"] + ["#14b8a6"] * 6
    for index, ((cx, cy), color) in enumerate(zip(centers, colors)):
        ax.add_patch(
            Circle(
                (cx, cy),
                GUARANTEED_RECEPTION_RADIUS_M,
                facecolor=color,
                edgecolor=color,
                alpha=0.13,
                linewidth=1.2,
                zorder=1,
            )
        )
        ax.scatter(cx, cy, color=color, edgecolor="white", s=85, zorder=4)
        ax.annotate(
            f"P{index}",
            (cx, cy),
            xytext=(7, 7),
            textcoords="offset points",
            fontsize=10,
            weight="bold",
            zorder=5,
        )

    route = centers[[0, 1, 2, 3, 4, 5, 6]]
    ax.plot(
        route[:, 0],
        route[:, 1],
        color="#7c3aed",
        linestyle="--",
        linewidth=1.7,
        label="Mandatory coverage backbone",
        zorder=3,
    )
    ax.scatter(
        worst[:, 0],
        worst[:, 1],
        marker="D",
        s=48,
        color="#dc2626",
        label="Worst boundary points",
        zorder=5,
    )

    ax.text(
        0.02,
        0.02,
        "Analytic maximum nearest-center distance\n"
        f"= {bound['worst_distance_m']:.2f} m\n"
        f"Guaranteed margin = {bound['minimum_margin_m']:.2f} m",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=11,
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "alpha": 0.92},
        zorder=6,
    )

    extent = TARGET_RADIUS_M + GUARANTEED_RECEPTION_RADIUS_M + 100.0
    ax.set_xlim(-extent, extent)
    ax.set_ylim(-extent, extent)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x / m")
    ax.set_ylabel("y / m")
    ax.set_title("Seven-point deterministic coverage geometry")
    ax.grid(alpha=0.18)
    ax.legend(loc="upper right")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "seven_point_disks.png",
    )
    args = parser.parse_args()
    make_figure(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
