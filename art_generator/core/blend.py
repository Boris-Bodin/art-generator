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
    """Compose ``top`` sur ``base`` selon ``mode`` et ``opacity`` (couche opaque)."""
    if mode not in _MODES:
        raise ValueError(f"Mode de fusion inconnu : {mode!r}")
    blended = _MODES[mode](base, top)
    out = base * (1.0 - opacity) + blended * opacity
    return np.clip(out, 0.0, 1.0)


def composite(
    base: np.ndarray,
    color: np.ndarray,
    alpha: np.ndarray,
    mode: str,
    opacity: float,
    model: str = "light",
) -> np.ndarray:
    """Compose une couche ``(color, alpha)`` sur ``base`` (Phase 4).

    ``alpha`` ``(H, W)`` est la couverture de la couche : là où elle vaut 0, le
    fond ``base`` transparaît intégralement — la forme est ainsi *découplée* du
    fond, quel qu'il soit (fin du fond noir implicite).

    Deux modèles de rendu :

    * ``"light"`` — light painting additif. Le mode de fusion agit sur la couleur,
      puis on mélange selon la couverture :
      ``out = base·(1-a) + mode(base, color)·a`` avec ``a = alpha·opacity``.
      Sur fond noir, ``color·a == color·alpha·opacity`` reproduit l'ancien rendu.
    * ``"ink"`` — encre soustractive. Le pigment ``color`` *absorbe* la lumière du
      support au lieu d'en ajouter : ``out = base·(1 - a·(1 - color))``. Des
      couches successives s'assombrissent (empilement multiplicatif), rendant des
      formes sombres lisibles sur fond clair.
    """
    if mode not in _MODES:
        raise ValueError(f"Mode de fusion inconnu : {mode!r}")
    a = np.clip(alpha * opacity, 0.0, 1.0)[..., None]

    if model == "ink":
        out = base * (1.0 - a * (1.0 - color))
    elif model == "light":
        blended = _MODES[mode](base, color)
        out = base * (1.0 - a) + blended * a
    else:
        raise ValueError(f"Modèle de rendu inconnu : {model!r}")

    return np.clip(out, 0.0, 1.0)
