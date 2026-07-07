"""Génération du fond de l'œuvre."""

from __future__ import annotations

import numpy as np

from .genome import ArtworkGenome


def make_background(genome: ArtworkGenome) -> np.ndarray:
    """Renvoie le tampon de fond ``(H, W, 3)`` dans ``[0, 1]``."""
    h, w = genome.height, genome.width
    kind = genome.background

    if kind == "black":
        return np.zeros((h, w, 3), dtype=np.float64)
    if kind == "white":
        return np.ones((h, w, 3), dtype=np.float64)
    if kind == "gradient":
        top = np.asarray(genome.background_params.get("top", (0.02, 0.02, 0.06)))
        bottom = np.asarray(genome.background_params.get("bottom", (0.0, 0.0, 0.0)))
        ramp = np.linspace(0.0, 1.0, h).reshape(h, 1, 1)
        grad = top * (1.0 - ramp) + bottom * ramp
        return np.broadcast_to(grad, (h, w, 3)).copy()

    raise ValueError(f"Type de fond inconnu : {kind!r}")
