"""Générateur pseudo-aléatoire déterministe.

Toute l'aléa du moteur transite par cette classe afin qu'une seed reconstruise
*exactement* la même œuvre. On s'appuie sur le ``Generator`` PCG64 de NumPy,
robuste et reproductible entre plateformes.
"""

from __future__ import annotations

import numpy as np


class RNG:
    """Enveloppe déterministe autour de ``numpy.random.Generator``."""

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self._gen = np.random.default_rng(self.seed)

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """Réel dans ``[low, high)``."""
        return float(self._gen.uniform(low, high))

    def randint(self, low: int, high: int) -> int:
        """Entier dans ``[low, high]`` (bornes incluses)."""
        return int(self._gen.integers(low, high + 1))

    def choice(self, options: list, weights: list[float] | None = None):
        """Choix pondéré parmi ``options``."""
        p = None
        if weights is not None:
            w = np.asarray(weights, dtype=float)
            p = w / w.sum()
        idx = int(self._gen.choice(len(options), p=p))
        return options[idx]

    def chance(self, probability: float) -> bool:
        """Vrai avec la probabilité donnée."""
        return self._gen.random() < probability

    def normal(self, mean: float = 0.0, std: float = 1.0) -> float:
        return float(self._gen.normal(mean, std))

    @property
    def generator(self) -> np.random.Generator:
        """Accès direct au générateur NumPy (pour tirages vectorisés)."""
        return self._gen
