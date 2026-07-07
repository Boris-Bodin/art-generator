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


def apply(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Point d'entrée du moteur : dispatch selon ``palette.mode``."""
    if palette.mode == "cosine":
        return cosine_palette(t, palette)
    raise ValueError(f"Mode de palette inconnu : {palette.mode!r}")


def random_palette(rng) -> PaletteGenome:
    """Palette cosinus harmonieuse tirée depuis un RNG.

    ``offset`` et ``amp`` restent dans des plages qui garantissent des couleurs
    vives sans écrêtage brutal ; les phases décalées entre canaux créent des
    dégradés riches.
    """
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
