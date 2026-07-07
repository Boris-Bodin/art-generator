"""Utilitaires mathématiques partagés."""

from __future__ import annotations

import numpy as np


def clean_points(points: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Retire les points non finis (singularités) et les valeurs associées."""
    mask = np.isfinite(points).all(axis=1) & np.isfinite(values)
    return points[mask], values[mask]


def fit_to_canvas(
    points: np.ndarray,
    width: int,
    height: int,
    margin: float = 0.08,
    percentile: float = 1.0,
) -> np.ndarray:
    """Normalise des points bruts vers des coordonnées pixel entières.

    Le cadrage est *robuste* : il s'appuie sur des percentiles pour ignorer les
    valeurs aberrantes, et préserve le rapport d'aspect (échelle commune aux deux
    axes) pour ne pas déformer l'œuvre.

    Returns:
        Tableau ``(M, 2)`` d'indices ``(x, y)`` entiers, déjà restreints au cadre.
    """
    x, y = points[:, 0], points[:, 1]
    lo_x, hi_x = np.percentile(x, (percentile, 100 - percentile))
    lo_y, hi_y = np.percentile(y, (percentile, 100 - percentile))

    cx, cy = (lo_x + hi_x) / 2.0, (lo_y + hi_y) / 2.0
    span = max(hi_x - lo_x, hi_y - lo_y, 1e-9)
    scale = (1.0 - 2.0 * margin) * min(width, height) / span

    px = (x - cx) * scale + width / 2.0
    py = (y - cy) * scale + height / 2.0

    xi = np.floor(px).astype(np.int64)
    yi = np.floor(py).astype(np.int64)

    inside = (xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)
    return np.column_stack((xi[inside], yi[inside])), inside
