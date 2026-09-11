from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon

from common import BLUE, GREEN, RED, Point, save, setup


def main() -> None:
    setup()
    side = 2.0
    height = math.sqrt(3.0)
    vertices = [Point(-1.0, 0.0), Point(1.0, 0.0), Point(0.0, height)]
    centre = Point(0.0, height / 3.0)
    circumradius = side / math.sqrt(3.0)

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.add_patch(
        Polygon(
            [(point.x, point.y) for point in vertices],
            closed=True,
            facecolor="#B7C9B6",
            edgecolor=GREEN,
            linewidth=2.0,
            alpha=0.55,
        )
    )
    ax.add_patch(
        Circle((centre.x, centre.y), side / 2.0, fill=False, edgecolor=RED, linewidth=2.0, linestyle="--")
    )
    ax.add_patch(
        Circle((centre.x, centre.y), circumradius, fill=False, edgecolor=BLUE, linewidth=2.0)
    )
    ax.plot([-1.0, 1.0], [0.0, 0.0], color="#263746", linewidth=2.6)
    ax.text(0.0, -0.13, r"diameter of region $=D$", ha="center")
    ax.annotate(
        "vertex outside\nthe D-diameter circle",
        xy=(0.0, height),
        xytext=(0.65, 1.55),
        arrowprops={"arrowstyle": "->", "color": RED},
        color=RED,
    )
    ax.scatter([centre.x], [centre.y], color="#263746", s=20)
    ax.plot([1.18, 1.38], [0.42, 0.42], color=RED, linewidth=2.0, linestyle="--")
    ax.text(1.44, 0.42, r"diameter-$D$ circle", va="center", color=RED)
    ax.plot([1.18, 1.38], [0.20, 0.20], color=BLUE, linewidth=2.0)
    ax.text(1.44, 0.20, r"minimum circle: $2D/\sqrt{3}$", va="center", color=BLUE)
    ax.set(xlim=(-1.45, 2.25), ylim=(-0.68, 2.05))
    ax.set_aspect("equal")
    ax.axis("off")
    save(fig, "fig4_jung_equilateral_counterexample")


if __name__ == "__main__":
    main()
