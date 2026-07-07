"""Courbes paramétriques.

Forme générale (tous les paramètres sont générés depuis le génome) :

    x(t) = sin(a·t) + b·sin(c·t + phi) + d·cos(e·t²)
    y(t) = cos(f·t) + g·cos(h·t + psi) + i·sin(j·t²)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation


class ParametricCurve(Equation):
    """Courbe paramétrique harmonique à termes quadratiques."""

    family = "parametric"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        t = np.linspace(0.0, float(p.get("t_max", 6.28318 * 8)), n)

        a, b, c = p["a"], p["b"], p["c"]
        d, e = p["d"], p["e"]
        f, g, h = p["f"], p["g"], p["h"]
        i_, j = p["i"], p["j"]
        phi, psi = p["phi"], p["psi"]

        x = np.sin(a * t) + b * np.sin(c * t + phi) + d * np.cos(e * t * t)
        y = np.cos(f * t) + g * np.cos(h * t + psi) + i_ * np.sin(j * t * t)

        points = np.column_stack((x, y))
        values = np.clip(t / t[-1], 0.0, 1.0)
        return points, values


def default_params(rng) -> dict[str, Any]:
    """Paramètres harmonieux tirés depuis un :class:`~art_generator.core.rng.RNG`.

    Les fréquences restent proches d'entiers pour favoriser des courbes fermées
    et lisibles ; les termes quadratiques ont un coefficient volontairement
    faible pour éviter un repliement trop chaotique.
    """
    return {
        "a": rng.randint(1, 5),
        "b": rng.uniform(0.3, 1.2),
        "c": rng.randint(2, 9),
        "d": rng.uniform(0.1, 0.6),
        "e": rng.uniform(0.02, 0.18),
        "f": rng.randint(1, 5),
        "g": rng.uniform(0.3, 1.2),
        "h": rng.randint(2, 9),
        "i": rng.uniform(0.1, 0.6),
        "j": rng.uniform(0.02, 0.18),
        "phi": rng.uniform(0.0, 6.28318),
        "psi": rng.uniform(0.0, 6.28318),
        "t_max": 6.28318 * rng.randint(6, 16),
    }
