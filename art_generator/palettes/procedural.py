"""Palettes procédurales.

Les couleurs ne sont jamais choisies dans une liste : elles sont *calculées*.
La palette par défaut est un gradient cosinus (Inigo Quilez) :

    couleur(t) = offset + amp * cos(2*pi * (freq * t + phase))

appliqué canal par canal. Ce modèle produit des dégradés cycliques doux et une
grande diversité tout en gardant une cohérence de famille.
"""

from __future__ import annotations

import numpy as np

from ..core.genome import PaletteGenome

_TWO_PI = 2.0 * np.pi


def cosine_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Mappe un tableau de valeurs ``t in [0, 1]`` vers des couleurs RGB.

    Returns:
        Tableau ``(N, 3)`` de flottants dans ``[0, 1]``.
    """
    t = np.asarray(t, dtype=np.float64).reshape(-1, 1)
    offset = np.asarray(palette.offset, dtype=np.float64)
    amp = np.asarray(palette.amp, dtype=np.float64)
    freq = np.asarray(palette.freq, dtype=np.float64)
    phase = np.asarray(palette.phase, dtype=np.float64)

    rgb = offset + amp * np.cos(_TWO_PI * (freq * t + phase))
    return np.clip(rgb, 0.0, 1.0)


def hsv_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Palette HSV : la teinte parcourt ``hue`` le long de ``t``.

    Saturation et valeur sont constantes. Conversion HSV→RGB vectorisée.
    """
    t = np.asarray(t, dtype=np.float64)
    h = (palette.hue[0] + t * palette.hue[1]) % 1.0
    s = np.full_like(h, palette.sat)
    v = np.full_like(h, palette.val)

    i = np.floor(h * 6.0).astype(np.int64)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    tt = v * (1.0 - (1.0 - f) * s)
    i = i % 6

    r = np.choose(i, [v, q, p, p, tt, v])
    g = np.choose(i, [tt, v, v, q, p, p])
    b = np.choose(i, [p, p, tt, v, v, q])
    return np.clip(np.column_stack((r, g, b)), 0.0, 1.0)


def hsl_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Palette HSL : teinte parcourant ``hue``, ``sat`` fixe, luminosité = ``val``.

    Contrairement au HSV, le HSL rend la luminosité (``L``) symétrique : ``L=0.5``
    donne la couleur la plus saturée, ``L→1`` tend vers le blanc. On réutilise le
    champ ``val`` du génome comme luminosité ``L``.
    """
    t = np.asarray(t, dtype=np.float64)
    h = (palette.hue[0] + t * palette.hue[1]) % 1.0
    s = palette.sat
    lightness = palette.val

    c = (1.0 - abs(2.0 * lightness - 1.0)) * s
    hp = h * 6.0
    x = c * (1.0 - np.abs(hp % 2.0 - 1.0))
    m = lightness - c / 2.0

    zeros = np.zeros_like(h)
    seg = np.floor(hp).astype(np.int64) % 6
    r = np.choose(seg, [c, x, zeros, zeros, x, c]) + m
    g = np.choose(seg, [x, c, c, x, zeros, zeros]) + m
    b = np.choose(seg, [zeros, zeros, x, c, c, x]) + m
    return np.clip(np.column_stack((r, g, b)), 0.0, 1.0)


def gradient_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Dégradé multi-arrêts : interpolation linéaire entre arrêts ``(pos, r, g, b)``."""
    t = np.asarray(t, dtype=np.float64)
    stops = sorted(palette.stops, key=lambda s: s[0])
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1:] for s in stops])  # (S, 3)
    r = np.interp(t, pos, cols[:, 0])
    g = np.interp(t, pos, cols[:, 1])
    b = np.interp(t, pos, cols[:, 2])
    return np.clip(np.column_stack((r, g, b)), 0.0, 1.0)


def apply(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Point d'entrée du moteur : dispatch selon ``palette.mode``."""
    if palette.mode == "cosine":
        return cosine_palette(t, palette)
    if palette.mode == "hsv":
        return hsv_palette(t, palette)
    if palette.mode == "hsl":
        return hsl_palette(t, palette)
    if palette.mode == "gradient":
        return gradient_palette(t, palette)
    raise ValueError(f"Mode de palette inconnu : {palette.mode!r}")


def _random_cosine(rng) -> PaletteGenome:
    base_phase = rng.uniform(0.0, 1.0)
    return PaletteGenome(
        mode="cosine",
        offset=(rng.uniform(0.4, 0.6), rng.uniform(0.4, 0.6), rng.uniform(0.4, 0.6)),
        amp=(rng.uniform(0.35, 0.55), rng.uniform(0.35, 0.55), rng.uniform(0.35, 0.55)),
        freq=(rng.uniform(0.7, 1.6), rng.uniform(0.7, 1.6), rng.uniform(0.7, 1.6)),
        phase=(
            base_phase,
            base_phase + rng.uniform(0.1, 0.4),
            base_phase + rng.uniform(0.4, 0.8),
        ),
    )


def _random_hsv(rng) -> PaletteGenome:
    return PaletteGenome(
        mode="hsv",
        hue=(rng.uniform(0.0, 1.0), rng.uniform(0.2, 0.9)),
        sat=rng.uniform(0.55, 0.95),
        val=rng.uniform(0.85, 1.0),
    )


def _random_hsl(rng) -> PaletteGenome:
    return PaletteGenome(
        mode="hsl",
        hue=(rng.uniform(0.0, 1.0), rng.uniform(0.2, 0.9)),
        sat=rng.uniform(0.55, 0.95),
        val=rng.uniform(0.45, 0.62),  # luminosité L : proche de 0.5 = couleurs vives
    )


def _random_gradient(rng) -> PaletteGenome:
    """Dégradé dont les arrêts sont échantillonnés sur une palette cosinus.

    Ancrer les couleurs sur un cosinus conserve la parenté chromatique de famille.
    """
    base = _random_cosine(rng)
    n_stops = rng.randint(3, 5)
    positions = sorted(rng.uniform(0.0, 1.0) for _ in range(n_stops))
    positions[0], positions[-1] = 0.0, 1.0
    sampled = cosine_palette(np.array(positions), base)
    stops = [[positions[i], *sampled[i].tolist()] for i in range(len(positions))]
    return PaletteGenome(mode="gradient", stops=stops)


def random_palette(rng) -> PaletteGenome:
    """Palette harmonieuse : cosinus (dominant), HSV, HSL ou dégradé multi-arrêts."""
    mode = rng.choice(
        ["cosine", "hsv", "hsl", "gradient"], weights=[0.5, 0.18, 0.16, 0.16]
    )
    if mode == "cosine":
        return _random_cosine(rng)
    if mode == "hsv":
        return _random_hsv(rng)
    if mode == "hsl":
        return _random_hsl(rng)
    return _random_gradient(rng)
