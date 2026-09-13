"""Differential bearing-only information and error-amplification metrics."""
import math
import numpy as np


def bearing_jacobian(sensor, target):
    dx, dy = np.asarray(target, float) - np.asarray(sensor, float)
    r2 = dx * dx + dy * dy
    if r2 < 1e-12:
        return np.array([0.0, 0.0])
    return np.array([-dy / r2, dx / r2])


def bearing_fim(sensors, target,
                sigma_rad=math.radians(1.0) / math.sqrt(3.0)):
    """FIM under an explicitly additional independent Gaussian approximation."""
    jac = np.vstack([bearing_jacobian(s, target) for s in sensors])
    return (jac.T @ jac) / (sigma_rad * sigma_rad)


def covariance_metrics(fim, ridge=1e-12):
    eig = np.linalg.eigvalsh(fim)
    if eig[0] <= ridge:
        return {"a": math.inf, "d": -math.inf, "e": 0.0,
                "gdop": math.inf}
    cov = np.linalg.inv(fim)
    a = float(np.trace(cov))
    return {"a": a, "d": float(np.linalg.slogdet(fim)[1]),
            "e": float(eig[0]), "gdop": math.sqrt(a)}


def bounded_linearized_diameter(sensors, target, half_width_rad):
    """Fast local proxy for the bounded-error feasible-set diameter."""
    jac = np.vstack([bearing_jacobian(s, target) for s in sensors])
    if jac.shape != (2, 2) or abs(np.linalg.det(jac)) < 1e-14:
        return math.inf
    inv = np.linalg.inv(jac)
    vertices = np.array([[sx, sy]
                         for sx in (-half_width_rad, half_width_rad)
                         for sy in (-half_width_rad, half_width_rad)]) @ inv.T
    delta = vertices[:, None, :] - vertices[None, :, :]
    return float(np.sqrt(np.max(np.sum(delta * delta, axis=-1))))

