"""Application de symétries sur un nuage de points.

Les opérations travaillent sur des points *centrés* (autour de l'origine) afin
que les rotations et miroirs soient géométriquement corrects. Les valeurs de
coloration sont répliquées à l'identique pour chaque copie.
"""

from __future__ import annotations

import numpy as np


def apply_symmetry(
    points: np.ndarray, values: np.ndarray, mode: str, order: int
) -> tuple[np.ndarray, np.ndarray]:
    """Réplique le nuage selon la symétrie demandée.

    Args:
        points: ``(N, 2)`` centrés sur l'origine.
        mode: ``none`` | ``mirror`` | ``radial`` | ``kaleidoscope``.
        order: nombre de secteurs pour les symétries radiales.
    """
    if mode == "none":
        return points, values

    if mode == "mirror":
        mirrored = points.copy()
        mirrored[:, 0] *= -1.0
        return np.vstack((points, mirrored)), np.concatenate((values, values))

    if mode in ("radial", "kaleidoscope"):
        order = max(2, int(order))
        copies_pts = []
        copies_val = []
        variants = [points]
        if mode == "kaleidoscope":
            reflected = points.copy()
            reflected[:, 0] *= -1.0
            variants.append(reflected)
        for base in variants:
            for k in range(order):
                ang = 2.0 * np.pi * k / order
                cos_a, sin_a = np.cos(ang), np.sin(ang)
                rx = base[:, 0] * cos_a - base[:, 1] * sin_a
                ry = base[:, 0] * sin_a + base[:, 1] * cos_a
                copies_pts.append(np.column_stack((rx, ry)))
                copies_val.append(values)
        return np.vstack(copies_pts), np.concatenate(copies_val)

    raise ValueError(f"Symétrie inconnue : {mode!r}")
