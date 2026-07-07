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
    center_on: str = "box",
) -> np.ndarray:
    """Normalise des points bruts vers des coordonnées pixel entières.

    Le cadrage est *robuste* : il s'appuie sur des percentiles pour ignorer les
    valeurs aberrantes, et préserve le rapport d'aspect (échelle commune aux deux
    axes) pour ne pas déformer l'œuvre.

    Deux stratégies de centrage/échelle (``center_on``) :

    * ``"box"`` — centre sur le milieu de la boîte des percentiles ; échelle sur
      son plus grand côté. Robuste et historique.
    * ``"density"`` — centre sur le **centroïde pondéré par la densité** (la
      moyenne des points, où les zones denses pèsent naturellement plus) et met
      à l'échelle sur un **rayon robuste** (percentile des distances au
      centroïde), pour cadrer sur le cœur de la forme plutôt que sur sa boîte.

    Returns:
        ``(coords, inside)`` : indices ``(x, y)`` entiers restreints au cadre, et
        le masque booléen des points conservés (aligné sur ``points``).
    """
    x, y = points[:, 0], points[:, 1]
    lo_x, hi_x = np.percentile(x, (percentile, 100 - percentile))
    lo_y, hi_y = np.percentile(y, (percentile, 100 - percentile))

    if center_on == "density":
        # Centroïde robuste : moyenne restreinte à la boîte des percentiles
        # (écarte les aberrations), donc pondérée par la densité des points.
        core = (x >= lo_x) & (x <= hi_x) & (y >= lo_y) & (y <= hi_y)
        if not core.any():
            core = np.ones_like(x, dtype=bool)
        cx, cy = float(x[core].mean()), float(y[core].mean())
        # Rayon robuste autour du centroïde : percentile des distances radiales.
        r = np.hypot(x[core] - cx, y[core] - cy)
        span = max(2.0 * float(np.percentile(r, 100 - percentile)), 1e-9)
    else:
        cx, cy = (lo_x + hi_x) / 2.0, (lo_y + hi_y) / 2.0
        span = max(hi_x - lo_x, hi_y - lo_y, 1e-9)

    scale = (1.0 - 2.0 * margin) * min(width, height) / span

    px = (x - cx) * scale + width / 2.0
    py = (y - cy) * scale + height / 2.0

    xi = np.floor(px).astype(np.int64)
    yi = np.floor(py).astype(np.int64)

    inside = (xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)
    return np.column_stack((xi[inside], yi[inside])), inside
