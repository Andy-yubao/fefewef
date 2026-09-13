"""Simulator-compatible observation outcomes for an omnidirectional source."""
import numpy as np


def noisy_bearing(sensor, target, error_rad):
    delta = np.asarray(target, float) - np.asarray(sensor, float)
    return float((np.arctan2(delta[1], delta[0]) + error_rad) % (2.0 * np.pi))


def observe(sensor, target, reception_radius, error_rad=0.0, near_radius=5.0):
    distance = float(np.linalg.norm(np.asarray(target, float) -
                                    np.asarray(sensor, float)))
    if distance > reception_radius:
        return {"kind": "no_signal", "bearing": None, "distance": distance}
    if distance <= near_radius:
        return {"kind": "near", "bearing": None, "distance": distance}
    return {"kind": "bearing",
            "bearing": noisy_bearing(sensor, target, error_rad),
            "distance": distance}

