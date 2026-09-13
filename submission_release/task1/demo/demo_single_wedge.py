from __future__ import annotations

import matplotlib.pyplot as plt

from common import BLUE, GREEN, Point, draw_wedge, observation, save, setup


def main() -> None:
    setup()
    sensor = Point(0.0, 0.0)
    target = Point(900.0, 520.0)
    obs = observation(sensor, target)

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    draw_wedge(ax, obs, 1250.0, alpha=0.34)
    ax.scatter([sensor.x], [sensor.y], color="#263746", s=38, zorder=4)
    ax.text(sensor.x - 55, sensor.y - 90, r"$S_i$", fontsize=12)
    ax.text(850, 560, r"$+1^\circ$", color="#5E6872")
    ax.text(880, 440, r"$-1^\circ$", color="#5E6872")
    ax.text(-18, -18, "检测点", color="#263746", ha="right", va="top")
    ax.set(xlabel="x / m", ylabel="y / m", xlim=(-120, 1180), ylim=(-120, 760))
    ax.set_aspect("equal")
    ax.grid(alpha=0.16)
    save(fig, "fig1_single_bearing_wedge")


if __name__ == "__main__":
    main()
