from __future__ import annotations

import math
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.patches import Arc as MplArc
from matplotlib.patches import Circle, Polygon, Wedge

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.q1 import Arc, BearingObservation, ClippedRegion, Point, Segment  # noqa: E402


FIGURE_DIR = Path(__file__).resolve().parents[1] / "figures"
BLUE = "#527B9D"
LIGHT_BLUE = "#AFC6D8"
GREEN = "#4F8A70"
RED = "#A75D5D"
GRAY = "#5E6872"


def setup() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.size": 10,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.family": "DejaVu Sans",
        }
    )
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def bearing(sensor: Point, target: Point) -> float:
    return math.degrees(math.atan2(target.y - sensor.y, target.x - sensor.x)) % 360.0


def observation(sensor: Point, target: Point) -> BearingObservation:
    return BearingObservation(sensor, bearing(sensor, target))


def draw_wedge(ax: Axes, obs: BearingObservation, reach: float, color: str = LIGHT_BLUE, alpha: float = 0.24) -> None:
    ax.add_patch(
        Wedge(
            (obs.sensor.x, obs.sensor.y),
            reach,
            obs.bearing_deg - obs.error_deg,
            obs.bearing_deg + obs.error_deg,
            facecolor=color,
            edgecolor="none",
            alpha=alpha,
        )
    )
    for angle, style in (
        (obs.bearing_deg - obs.error_deg, "--"),
        (obs.bearing_deg, "-"),
        (obs.bearing_deg + obs.error_deg, "--"),
    ):
        direction = math.radians(angle)
        ax.plot(
            [obs.sensor.x, obs.sensor.x + reach * math.cos(direction)],
            [obs.sensor.y, obs.sensor.y + reach * math.sin(direction)],
            linestyle=style,
            color=BLUE if style == "-" else GRAY,
            linewidth=1.2,
        )


def draw_region_boundary(ax: Axes, region: ClippedRegion, color: str = GREEN, linewidth: float = 2.2) -> None:
    for segment in region.segments:
        ax.plot(
            [segment.start.x, segment.end.x],
            [segment.start.y, segment.end.y],
            color=color,
            linewidth=linewidth,
        )
    for arc in region.arcs:
        theta1 = math.degrees(arc.start_angle)
        theta2 = math.degrees(arc.end_angle)
        ax.add_patch(
            MplArc(
                (0.0, 0.0),
                2.0 * arc.radius,
                2.0 * arc.radius,
                theta1=theta1,
                theta2=theta2,
                color=color,
                linewidth=linewidth,
            )
        )


def save(fig: plt.Figure, stem: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{stem}.png", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)

