"""Champs de vecteurs : advection de particules.

On définit un champ ``dx/dt = f(x, y)``, ``dy/dt = g(x, y)`` et on y transporte
des milliers de particules par intégration d'Euler. Chaque trajectoire trace une
ligne de courant ; l'ensemble dessine la structure du champ.

Le champ est composé de termes trigonométriques mélangés dont les coefficients
sont générés : c'est le mécanisme d'« invention » de nouveaux champs. Les
positions initiales des particules dérivent de ``params['seed']`` pour rester
reproductibles (l'équation n'a pas accès au RNG global).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation


class VectorField(Equation):
    """Champ de vecteurs advectant des particules le long de ses lignes de courant."""

    family = "vector_field"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        n_particles = int(p.get("n_particles", 2000))
        steps = max(4, n // n_particles)
        dt = float(p.get("dt", 0.02))

        a, b, c, d = p["a"], p["b"], p["c"], p["d"]
        rng = np.random.default_rng(int(p["seed"]))
        x = rng.uniform(-1.5, 1.5, n_particles)
        y = rng.uniform(-1.5, 1.5, n_particles)

        xs = np.empty((steps, n_particles), dtype=np.float64)
        ys = np.empty((steps, n_particles), dtype=np.float64)
        for s in range(steps):
            fx = np.sin(a * y) + c * np.cos(b * x)
            fy = np.sin(d * x) - np.cos(a * y)
            x = x + dt * fx
            y = y + dt * fy
            xs[s] = x
            ys[s] = y

        points = np.column_stack((xs.ravel(order="F"), ys.ravel(order="F")))
        # Coloration par « âge » de la particule le long de sa ligne de courant.
        age = np.tile(np.linspace(0.0, 1.0, steps), n_particles)
        return points, age


def default_params(rng) -> dict[str, Any]:
    return {
        "a": rng.uniform(1.0, 3.5),
        "b": rng.uniform(1.0, 3.5),
        "c": rng.uniform(0.4, 1.6),
        "d": rng.uniform(1.0, 3.5),
        "dt": rng.uniform(0.012, 0.03),
        "n_particles": rng.randint(1500, 3000),
        "seed": rng.randint(0, 2**31 - 1),
    }
