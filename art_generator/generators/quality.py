"""Contrôle de viabilité d'une équation.

De nombreux jeux de paramètres aléatoires produisent des formes dégénérées :
attracteurs qui s'effondrent en un point fixe, cycles trop pauvres, courbes
plates… On les détecte en rasterisant un échantillon sur une grille grossière et
en comptant les cellules occupées : une œuvre « dessinable » couvre une surface
significative.

Le rejet est déterministe (piloté par le RNG de la seed), donc reproductible.
"""

from __future__ import annotations

import numpy as np

from ..equations import registry
from ..utils.math_utils import clean_points

_GRID = 96
_MIN_CELLS = 220  # cellules occupées minimales sur une grille 96×96


def occupancy(points: np.ndarray) -> int:
    """Nombre de cellules occupées sur une grille normalisée ``_GRID``²."""
    points, _ = clean_points(points, np.zeros(len(points)))
    if len(points) < 16:
        return 0
    lo = np.percentile(points, 1, axis=0)
    hi = np.percentile(points, 99, axis=0)
    span = np.maximum(hi - lo, 1e-9)
    norm = (points - lo) / span
    cells = np.floor(np.clip(norm, 0, 0.9999) * _GRID).astype(np.int64)
    flat = cells[:, 0] * _GRID + cells[:, 1]
    return int(np.unique(flat).size)


def is_viable(family: str, params: dict, probe: int = 6000) -> bool:
    """Vrai si l'équation couvre assez de surface pour être dessinable."""
    equation = registry.build(family, params)
    points, _ = equation.sample(probe)
    return occupancy(points) >= _MIN_CELLS


def viable_params(family: str, rng, max_tries: int = 24) -> dict:
    """Tire des paramètres viables pour ``family`` (réessaie jusqu'à en trouver).

    Si aucun essai n'aboutit (rare), renvoie le dernier tirage : le moteur reste
    fonctionnel, l'œuvre est simplement moins riche.
    """
    params = registry.random_params(family, rng)
    for _ in range(max_tries):
        if is_viable(family, params):
            return params
        params = registry.random_params(family, rng)
    return params
