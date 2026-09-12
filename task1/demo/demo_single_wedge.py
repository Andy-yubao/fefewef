from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Wedge

from common import BLUE, LIGHT_BLUE, Point, setup


def polar(length: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return length * math.cos(angle), length * math.sin(angle)


def main() -> None:
    setup()
    plt.rcParams.update({"font.family": "sans-serif", "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(6.2, 3.4))

    centre_angle = 24.0
    display_error = 11.0  # 示意角仅为便于观察而放大，符号仍记为 epsilon。
    reach = 5.2
    sensor = Point(0.0, 0.0)
    edge_blue = "#2F648C"

    ax.add_patch(
        Wedge(
            (sensor.x, sensor.y),
            reach,
            centre_angle - display_error,
            centre_angle + display_error,
            facecolor="#8FAFC8",
            edgecolor="none",
            alpha=0.64,
        )
    )
    for offset, linestyle, width in (
        (-display_error, "--", 1.9),
        (0.0, "-", 2.4),
        (display_error, "--", 1.9),
    ):
        x, y = polar(reach, centre_angle + offset)
        ax.plot([0.0, x], [0.0, y], color=edge_blue, linestyle=linestyle, linewidth=width)

    ax.scatter([0.0], [0.0], s=30, color="#263746", zorder=4)

    ax.text(-0.18, -0.32, r"$S_i$", fontsize=11)
    ax.text(4.32, 2.82, r"$\hat\theta_i+\varepsilon$", fontsize=10, color=edge_blue, ha="right")
    ax.text(4.80, 0.95, r"$\hat\theta_i-\varepsilon$", fontsize=10, color=edge_blue, ha="right")

    ax.set_xlim(-0.45, 5.35)
    ax.set_ylim(-0.35, 3.35)
    ax.set_aspect("equal")
    ax.axis("off")
    figure_dir = Path(__file__).resolve().parents[1] / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(figure_dir / "fig1_single_bearing_wedge.svg", bbox_inches="tight")
    fig.savefig(figure_dir / "fig1_single_bearing_wedge.pdf", bbox_inches="tight")
    fig.savefig(figure_dir / "fig1_single_bearing_wedge.png", dpi=600, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
