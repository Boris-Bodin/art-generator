"""Attracteurs étranges à itération.

On itère une récurrence ``(x, y) -> (x', y')`` des milliers/millions de fois.
Le nuage de points résultant dessine la structure de l'attracteur.

Familles fournies :
  * ``clifford`` — attracteur de Clifford Pickover
  * ``dejong``   — attracteur de Peter de Jong
  * ``custom``   — attracteur « inventé » à termes trigonométriques mélangés

La récurrence est intrinsèquement séquentielle : elle est ici implémentée en
boucle NumPy sur des tampons pré-alloués. Une accélération Numba/GPU est prévue
(voir la feuille de route) sans changer cette interface.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation

_WARMUP = 100  # itérations écartées le temps que l'orbite rejoigne l'attracteur


def _iterate(step, x0: float, y0: float, n: int) -> np.ndarray:
    xs = np.empty(n, dtype=np.float64)
    ys = np.empty(n, dtype=np.float64)
    x, y = x0, y0
    for _ in range(_WARMUP):
        x, y = step(x, y)
    for k in range(n):
        x, y = step(x, y)
        xs[k] = x
        ys[k] = y
    return np.column_stack((xs, ys))


class Attractor(Equation):
    """Attracteur étrange générique paramétré par ``variant``."""

    family = "attractor"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        variant = p.get("variant", "clifford")
        a, b, c, d = p["a"], p["b"], p["c"], p["d"]

        if variant == "clifford":
            def step(x, y):
                return (
                    np.sin(a * y) + c * np.cos(a * x),
                    np.sin(b * x) + d * np.cos(b * y),
                )
        elif variant == "dejong":
            def step(x, y):
                return (
                    np.sin(a * y) - np.cos(b * x),
                    np.sin(c * x) - np.cos(d * y),
                )
        elif variant == "custom":
            e = p.get("e", 1.0)
            def step(x, y):
                return (
                    np.sin(a * y) + c * np.cos(a * x) - np.sin(e * y * x * 0.5),
                    np.cos(b * x) - d * np.sin(b * y) + np.sin(e * x),
                )
        else:  # pragma: no cover - garde-fou
            raise ValueError(f"Attracteur inconnu : {variant!r}")

        points = _iterate(step, 0.1, 0.0, n)
        values = self.velocity_values(points)
        return points, values


def default_params(rng) -> dict[str, Any]:
    variant = rng.choice(
        ["clifford", "dejong", "custom"], weights=[0.45, 0.35, 0.20]
    )
    return {
        "variant": variant,
        "a": rng.uniform(-2.2, 2.2),
        "b": rng.uniform(-2.2, 2.2),
        "c": rng.uniform(-2.2, 2.2),
        "d": rng.uniform(-2.2, 2.2),
        "e": rng.uniform(-1.5, 1.5),
    }
