"""Modes de fusion entre couches.

Chaque fonction combine un tampon ``base`` (le cumul déjà composé) et un tampon
``top`` (la nouvelle couche), tous deux ``(H, W, 3)`` en flottants ``[0, 1]``,
pondérés par l'opacité de la couche.
"""

from __future__ import annotations

import numpy as np


def _normal(base, top):
    return top


def _add(base, top):
    return base + top


def _screen(base, top):
    return 1.0 - (1.0 - base) * (1.0 - top)


def _multiply(base, top):
    return base * top


def _difference(base, top):
    return np.abs(base - top)


_MODES = {
    "normal": _normal,
    "add": _add,
    "screen": _screen,
    "multiply": _multiply,
    "difference": _difference,
}


def blend(base: np.ndarray, top: np.ndarray, mode: str, opacity: float) -> np.ndarray:
    """Compose ``top`` sur ``base`` selon ``mode`` et ``opacity``."""
    if mode not in _MODES:
        raise ValueError(f"Mode de fusion inconnu : {mode!r}")
    blended = _MODES[mode](base, top)
    out = base * (1.0 - opacity) + blended * opacity
    return np.clip(out, 0.0, 1.0)
