"""Coordonnées polaires : r = f(theta).

Couvre roses, rosaces et spirales via une somme d'harmoniques sinus/cosinus,
plus une composante spirale optionnelle.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation


class PolarCurve(Equation):
    """Courbe polaire ``r(theta)`` combinant harmoniques et spirale."""

    family = "polar"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        turns = float(p.get("turns", 12))
        theta = np.linspace(0.0, 2.0 * np.pi * turns, n)

        k1, k2 = p["k1"], p["k2"]
        a1, a2 = p["a1"], p["a2"]
        base = float(p.get("base", 1.0))
        spiral = float(p.get("spiral", 0.0))

        r = base + a1 * np.cos(k1 * theta) + a2 * np.sin(k2 * theta)
        r = r + spiral * theta

        x = r * np.cos(theta)
        y = r * np.sin(theta)

        points = np.column_stack((x, y))
        values = np.clip(theta / theta[-1], 0.0, 1.0)
        return points, values


def default_params(rng) -> dict[str, Any]:
    spiral = rng.uniform(0.0, 0.05) if rng.chance(0.4) else 0.0
    return {
        "k1": rng.randint(2, 12),
        "k2": rng.randint(2, 12),
        "a1": rng.uniform(0.4, 1.0),
        "a2": rng.uniform(0.2, 0.8),
        "base": rng.uniform(0.2, 1.0),
        "spiral": spiral,
        "turns": rng.randint(6, 24),
    }
