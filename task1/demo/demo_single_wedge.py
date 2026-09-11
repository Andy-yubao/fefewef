from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Wedge

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

    ax.add_patch(
        Wedge(
            (sensor.x, sensor.y),
            reach,
            centre_angle - display_error,
            centre_angle + display_error,
            facecolor=LIGHT_BLUE,
            edgecolor="none",
            alpha=0.58,
        )
    )
    for offset, linestyle, width in (
        (-display_error, "--", 1.15),
        (0.0, "-", 1.45),
        (display_error, "--", 1.15),
    ):
        x, y = polar(reach, centre_angle + offset)
        ax.plot([0.0, x], [0.0, y], color=BLUE, linestyle=linestyle, linewidth=width)

    candidate_angle = centre_angle + 4.0
    candidate = polar(4.1, candidate_angle)
    ax.scatter([0.0], [0.0], s=30, color="#263746", zorder=4)
    ax.scatter([candidate[0]], [candidate[1]], s=28, color="#263746", zorder=4)
    ax.plot(
        [0.0, candidate[0]],
        [0.0, candidate[1]],
        color="#263746",
        linewidth=0.8,
        alpha=0.65,
    )

    ax.add_patch(
        Arc((0.0, 0.0), 2.0, 2.0, theta1=0.0, theta2=centre_angle, color="#596773", linewidth=1.0)
    )
    ax.add_patch(
        Arc(
            (0.0, 0.0),
            2.8,
            2.8,
            theta1=centre_angle,
            theta2=centre_angle + display_error,
            color="#A75D5D",
            linewidth=1.0,
        )
    )
    ax.add_patch(
        Arc(
            (0.0, 0.0),
            2.35,
            2.35,
            theta1=centre_angle - display_error,
            theta2=centre_angle,
            color="#A75D5D",
            linewidth=1.0,
        )
    )

    ax.text(-0.18, -0.32, r"$S_i$", fontsize=11)
    ax.text(candidate[0] + 0.10, candidate[1] + 0.05, r"$X$", fontsize=11)
    ax.text(1.12, 0.18, r"$\hat\theta_i$", fontsize=10, color="#263746")
    ax.text(1.42, 0.76, r"$\varepsilon$", fontsize=10, color="#A75D5D")
    ax.text(1.16, 0.36, r"$\varepsilon$", fontsize=10, color="#A75D5D")
    ax.text(3.30, 1.90, r"$W_i$", fontsize=12, color="#376F5B")
    ax.text(4.32, 2.82, r"$\hat\theta_i+\varepsilon$", fontsize=9, color=BLUE, ha="right")
    ax.text(4.80, 0.95, r"$\hat\theta_i-\varepsilon$", fontsize=9, color=BLUE, ha="right")
    # 论文标注统一保持水平，几何方向由连线本身表达，避免文字随斜线倾斜。
    ax.text(2.55, 1.38, r"$X-S_i$", fontsize=9, color="#263746", rotation=0)

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
