"""Domaines complexes : transformations conformes du plan.

On échantillonne un maillage de points ``z`` dans le disque unité, puis on
applique une fonction complexe ``w = f(z)`` (éventuellement itérée quelques fois)
et on trace ``(Re w, Im w)``. Les fonctions holomorphes déforment le maillage en
webs conformes caractéristiques.

Variantes de ``f`` :
  * ``poly``     — ``w = z**k + c``
  * ``sinus``    — ``w = sin(z) + c*z``
  * ``rational`` — ``w = (z + c) / (1 + conj(c)*z)`` (type Möbius)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation


class ComplexMap(Equation):
    """Transformation complexe d'un maillage du disque unité."""

    family = "complex"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        variant = p.get("variant", "sinus")
        c = complex(p["cx"], p["cy"])
        k = float(p.get("k", 2.0))
        iters = int(p.get("iters", 2))

        rng = np.random.default_rng(int(p["seed"]))
        # Maillage : anneaux concentriques remplissant le disque (structure lisible).
        radius = np.sqrt(rng.uniform(0.0, 1.0, n))
        angle = rng.uniform(0.0, 2.0 * np.pi, n)
        z = radius * np.exp(1j * angle)
        z0 = z.copy()

        for _ in range(max(1, iters)):
            if variant == "poly":
                z = z**k + c
            elif variant == "sinus":
                z = np.sin(z) + c * z
            elif variant == "rational":
                z = (z + c) / (1.0 + np.conj(c) * z + 1e-9)
            else:  # pragma: no cover
                raise ValueError(f"Variante complexe inconnue : {variant!r}")

        points = np.column_stack((z.real, z.imag))
        # Coloration par argument initial : révèle la déformation angulaire.
        values = (np.angle(z0) + np.pi) / (2.0 * np.pi)
        return points, values


def default_params(rng) -> dict[str, Any]:
    variant = rng.choice(["poly", "sinus", "rational"], weights=[0.3, 0.4, 0.3])
    return {
        "variant": variant,
        "cx": rng.uniform(-1.0, 1.0),
        "cy": rng.uniform(-1.0, 1.0),
        "k": rng.choice([2.0, 3.0, 4.0]) if variant == "poly" else 2.0,
        "iters": rng.randint(1, 3),
        "seed": rng.randint(0, 2**31 - 1),
    }
