"""Contrôle de viabilité d'une équation.

De nombreux jeux de paramètres aléatoires produisent des formes dégénérées :
attracteurs qui s'effondrent en un point fixe, cycles trop pauvres, courbes
plates… On les détecte en rasterisant un échantillon sur une grille et en
appliquant **deux** critères complémentaires :

* **Occupation** — nombre de cellules occupées sur une grille ``_GRID``² : une
  œuvre « dessinable » couvre une surface significative.
* **Dimension de box-counting** — pente log-log de l'occupation à plusieurs
  résolutions de grille (≈ 1 pour une courbe, ≈ 2 pour un remplissage surfacique).
  L'occupation seule ne distingue pas un nuage 2D d'une **courbe quasi-1D** : une
  ligne fine ou un cercle qui serpentent occupent beaucoup de cellules tout en
  restant unidimensionnels. La dimension rejette ces formes que l'occupation
  laissait passer, **sans** écarter les familles filamentaires légitimes (rosaces,
  courbes, champs de vecteurs), qui replient assez leurs traits pour dépasser
  nettement le seuil.

Le rejet est déterministe (piloté par le RNG de la seed), donc reproductible.
"""

from __future__ import annotations

import numpy as np

from ..equations import registry
from ..utils.math_utils import clean_points

_GRID = 96
_MIN_CELLS = 220  # cellules occupées minimales sur une grille 96×96
# Grilles de l'estimation de dimension (multi-échelle) ; la plus fine == _GRID.
_DIM_GRIDS = (24, 48, 96)
# Plancher de dimension : dans le « creux » empirique séparant les dégénérescences
# quasi-1D (D ≲ 0,65) des courbes légitimes (D ≳ 1,0). Rejette ~3 % des tirages.
_MIN_DIMENSION = 0.8


def _normalized(points: np.ndarray) -> np.ndarray | None:
    """Nettoie et normalise le nuage dans ``[0, 1)²`` (bornes robustes 1–99 %).

    Renvoie ``None`` si le nuage est trop pauvre pour être jugé.
    """
    points, _ = clean_points(points, np.zeros(len(points)))
    if len(points) < 16:
        return None
    lo = np.percentile(points, 1, axis=0)
    hi = np.percentile(points, 99, axis=0)
    span = np.maximum(hi - lo, 1e-9)
    return np.clip((points - lo) / span, 0, 0.9999)


def _occupied_cells(norm: np.ndarray, grid: int) -> int:
    """Nombre de cellules distinctes occupées sur une grille ``grid``²."""
    cells = np.floor(norm * grid).astype(np.int64)
    flat = cells[:, 0] * grid + cells[:, 1]
    return int(np.unique(flat).size)


def _box_dimension(counts: list[int]) -> float:
    """Dimension de box-counting : pente de ``log(occupation)`` vs ``log(grille)``."""
    logs = np.log(np.maximum(counts, 1))
    return float(np.polyfit(np.log(_DIM_GRIDS), logs, 1)[0])


def occupancy(points: np.ndarray) -> int:
    """Nombre de cellules occupées sur une grille normalisée ``_GRID``²."""
    norm = _normalized(points)
    if norm is None:
        return 0
    return _occupied_cells(norm, _GRID)


def box_dimension(points: np.ndarray) -> float:
    """Dimension de box-counting du nuage (≈ 1 courbe, ≈ 2 surface ; 0 si vide)."""
    norm = _normalized(points)
    if norm is None:
        return 0.0
    return _box_dimension([_occupied_cells(norm, g) for g in _DIM_GRIDS])


def is_viable(family: str, params: dict, probe: int = 6000) -> bool:
    """Vrai si l'équation couvre assez de surface **et** n'est pas quasi-1D."""
    equation = registry.build(family, params)
    points, _ = equation.sample(probe)
    norm = _normalized(points)
    if norm is None:
        return False
    counts = [_occupied_cells(norm, g) for g in _DIM_GRIDS]
    if counts[-1] < _MIN_CELLS:  # occupation surfacique (grille _GRID² == _DIM_GRIDS[-1])
        return False
    return _box_dimension(counts) >= _MIN_DIMENSION


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
