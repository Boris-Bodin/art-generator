"""Génération du fond de l'œuvre.

Depuis la Phase 4, le compositing par alpha (``core/blend.py::composite``) laisse
transparaître le fond dans les zones vides des couches : le fond redevient donc
un vrai élément de composition. On propose des fonds unis, des dégradés
**directionnels** et **radiaux**, ainsi qu'une **vignette** optionnelle
applicable à n'importe quel fond.
"""

from __future__ import annotations

import numpy as np

from .genome import ArtworkGenome


def make_background(genome: ArtworkGenome) -> np.ndarray:
    """Renvoie le tampon de fond ``(H, W, 3)`` dans ``[0, 1]``."""
    h, w = genome.height, genome.width
    kind = genome.background
    params = genome.background_params or {}

    if kind == "black":
        bg = np.zeros((h, w, 3), dtype=np.float64)
    elif kind == "white":
        bg = np.ones((h, w, 3), dtype=np.float64)
    elif kind == "gradient":
        bg = _gradient(h, w, params)
    elif kind == "radial":
        bg = _radial(h, w, params)
    else:
        raise ValueError(f"Type de fond inconnu : {kind!r}")

    vignette = float(params.get("vignette", 0.0))
    if vignette > 0.0:
        bg = _apply_vignette(bg, vignette)
    return np.clip(bg, 0.0, 1.0)


def _norm_coords(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées normalisées ``(xn, yn)`` dans ``[0, 1]``, forme ``(H, W)``."""
    xn = np.linspace(0.0, 1.0, w).reshape(1, w)
    yn = np.linspace(0.0, 1.0, h).reshape(h, 1)
    return np.broadcast_to(xn, (h, w)), np.broadcast_to(yn, (h, w))


def _gradient(h: int, w: int, params: dict) -> np.ndarray:
    """Dégradé linéaire entre ``top`` et ``bottom``.

    Sans ``angle`` (défaut), dégradé vertical historique (haut → bas). Avec
    ``angle`` (degrés, 0 = horizontal gauche→droite, 90 = vertical), dégradé
    **directionnel** projeté sur la direction voulue.
    """
    top = np.asarray(params.get("top", (0.02, 0.02, 0.06)), dtype=np.float64)
    bottom = np.asarray(params.get("bottom", (0.0, 0.0, 0.0)), dtype=np.float64)
    angle = params.get("angle")

    if angle is None:
        ramp = np.linspace(0.0, 1.0, h).reshape(h, 1, 1)
        grad = top * (1.0 - ramp) + bottom * ramp
        return np.broadcast_to(grad, (h, w, 3)).copy()

    theta = np.radians(float(angle))
    xn, yn = _norm_coords(h, w)
    proj = np.cos(theta) * xn + np.sin(theta) * yn
    lo, hi = proj.min(), proj.max()
    t = ((proj - lo) / max(hi - lo, 1e-9))[..., None]
    return top * (1.0 - t) + bottom * t


def _radial(h: int, w: int, params: dict) -> np.ndarray:
    """Dégradé radial de ``inner`` (centre) vers ``outer`` (bord).

    Le centre ``(cx, cy)`` et le ``radius`` sont exprimés en fractions ; la
    distance est normalisée par la plus petite dimension pour rester circulaire
    quel que soit le rapport d'aspect.
    """
    inner = np.asarray(params.get("inner", (0.06, 0.06, 0.12)), dtype=np.float64)
    outer = np.asarray(params.get("outer", (0.0, 0.0, 0.0)), dtype=np.float64)
    cx = float(params.get("cx", 0.5))
    cy = float(params.get("cy", 0.5))
    radius = float(params.get("radius", 0.75))

    xn, yn = _norm_coords(h, w)
    aspect = w / h
    d = np.hypot((xn - cx) * aspect, yn - cy)
    t = np.clip(d / max(radius, 1e-9), 0.0, 1.0)[..., None]
    return inner * (1.0 - t) + outer * t


def _apply_vignette(bg: np.ndarray, strength: float) -> np.ndarray:
    """Assombrit les bords : facteur ``1 - strength·d²`` (d = distance au centre)."""
    h, w = bg.shape[:2]
    xn, yn = _norm_coords(h, w)
    d = np.hypot(xn - 0.5, yn - 0.5) / np.hypot(0.5, 0.5)
    factor = 1.0 - strength * np.clip(d, 0.0, 1.0) ** 2
    return bg * factor[..., None]
