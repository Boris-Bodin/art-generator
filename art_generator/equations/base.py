"""Interface commune à toutes les familles d'équations.

Le moteur repose sur un modèle unifié : *toute* équation, quelle que soit sa
famille (paramétrique, polaire, attracteur, champ de vecteurs, complexe…),
produit un **nuage de points 2D** accompagné d'une **valeur scalaire par point**.

C'est ce dénominateur commun qui permet à un unique renderer par accumulation
lumineuse de donner à toutes les œuvres une identité visuelle partagée, tout en
autorisant l'ajout illimité de nouvelles familles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class Equation(ABC):
    """Base de toute équation générant un nuage de points.

    Les sous-classes reçoivent leurs paramètres via ``params`` (issus du génome)
    et implémentent :meth:`sample`.
    """

    #: Identifiant de famille, utilisé par le registre.
    family: str = "base"

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params

    @abstractmethod
    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Échantillonne ``n`` points.

        Returns:
            points: tableau ``(N, 2)`` de coordonnées brutes (non normalisées).
            values: tableau ``(N,)`` dans ``[0, 1]`` pour la coloration.

        Les points peuvent contenir des ``NaN``/``inf`` (singularités) : ils
        sont filtrés en aval par le moteur.
        """

    @staticmethod
    def velocity_values(points: np.ndarray) -> np.ndarray:
        """Valeur de coloration basée sur la vitesse (distance inter-points).

        Donne des dégradés naturels qui révèlent la dynamique de la courbe ou de
        l'attracteur. Résultat normalisé dans ``[0, 1]`` par percentiles.
        """
        deltas = np.diff(points, axis=0, prepend=points[:1])
        speed = np.hypot(deltas[:, 0], deltas[:, 1])
        finite = np.isfinite(speed)
        if not finite.any():
            return np.zeros(len(points))
        lo, hi = np.percentile(speed[finite], (2, 98))
        if hi - lo < 1e-12:
            return np.zeros(len(points))
        return np.clip((speed - lo) / (hi - lo), 0.0, 1.0)

    @staticmethod
    def arc_length_values(points: np.ndarray) -> np.ndarray:
        """Valeur de coloration = longueur d'arc cumulée le long de la trajectoire.

        Contrairement à :meth:`velocity_values` (dérivée locale), on intègre la
        distance parcourue depuis le premier point, normalisée dans ``[0, 1]`` :
        la couleur progresse continûment du début à la fin de la courbe, pour des
        rubans à dégradé chromatique. Les longueurs de segment sont bridées au 99e
        percentile pour qu'un saut singulier ne comprime pas tout le dégradé.

        N'a de sens que pour une **orbite unique** (attractor, parametric, polar,
        complex) : sur des trajectoires concaténées (particles, streamlines) le
        cumul saute entre segments et produit un dégradé par bandes.
        """
        deltas = np.diff(points, axis=0, prepend=points[:1])
        seg = np.hypot(deltas[:, 0], deltas[:, 1])
        seg[~np.isfinite(seg)] = 0.0
        if seg.size:
            cap = np.percentile(seg, 99.0)
            if cap > 0:
                seg = np.minimum(seg, cap)
        cumulative = np.cumsum(seg)
        total = cumulative[-1] if cumulative.size else 0.0
        if total < 1e-12:
            return np.zeros(len(points))
        return cumulative / total
