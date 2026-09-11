"""Angle helpers using radians internally."""
import math
import numpy as np


TAU = 2.0 * math.pi


def wrap_rad(x):
    return np.mod(x, TAU)


def angle_diff(a, b):
    """Signed smallest difference a-b in [-pi, pi)."""
    return (np.asarray(a) - np.asarray(b) + math.pi) % TAU - math.pi


def bearing(source, target):
    d = np.asarray(target, dtype=float) - np.asarray(source, dtype=float)
    return np.arctan2(d[..., 1], d[..., 0]) % TAU


def intersection_angle(sensor1, sensor2, target):
    """Acute line-intersection angle in [0, pi/2]."""
    a = bearing(target, sensor1)
    b = bearing(target, sensor2)
    d = np.abs(angle_diff(a, b))
    return np.minimum(d, math.pi - d)

