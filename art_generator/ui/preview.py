"""Aperçu rapide d'un génome — logique pure, sans toolkit graphique.

L'aperçu « temps réel » de l'UI repose sur une astuce d'échelle : le nombre de
points d'un génome est fixe, et le moteur est **indépendant de la résolution**
au-dessus d'un côté de référence (1600 px) mais *inchangé en deçà* (facteur
d'échelle planché à 1, cf. :meth:`Engine._scale`). En rendant le génome à une
petite taille (≈ 560 px), on obtient donc une image **fidèle** à l'œuvre finale
— même densité, même palette — mais bien plus rapide à calculer.

Ce module ne dépend que du moteur et de PIL : il est testable sans écran.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from math import gcd

from PIL import Image

from ..core.engine import Engine
from ..core.genome import ArtworkGenome

DEFAULT_MAX_SIDE = 1600
# Plafond de points pour un aperçu **vif** pendant l'édition. Réduire le nombre de
# points accélère le rendu au prix d'une densité un peu moindre : acceptable pour
# une prévisualisation interactive ; l'export final utilise le génome complet.
DRAFT_POINT_CAP = 150_000


def preview_dimensions(width: int, height: int, max_side: int = DEFAULT_MAX_SIDE) -> tuple[int, int]:
    """Dimensions d'aperçu : grand côté ramené à ``max_side``, ratio préservé.

    Ne **jamais agrandir** : un génome déjà plus petit que ``max_side`` est rendu
    à sa taille native.
    """
    long_edge = max(width, height)
    if long_edge <= max_side:
        return int(width), int(height)
    scale = max_side / long_edge
    return max(1, round(width * scale)), max(1, round(height * scale))


def dimensions_for(resolution: int, ratio: str) -> tuple[int, int]:
    """Dimensions (largeur, hauteur) pour un ``resolution`` (grand côté) et un ratio.

    ``ratio`` est un rapport d'aspect ``"largeur:hauteur"`` (ex. ``"16:9"``,
    ``"1:1"``). Le **grand côté** vaut toujours ``resolution`` ; l'autre en
    découle, arrêté à au moins 1 px.
    """
    rw, rh = (float(x) for x in ratio.split(":"))
    if rw <= 0 or rh <= 0:
        raise ValueError(f"Ratio invalide : {ratio!r}")
    resolution = int(resolution)
    if rw >= rh:
        return resolution, max(1, round(resolution * rh / rw))
    return max(1, round(resolution * rw / rh)), resolution


def simplify_ratio(width: int, height: int) -> str:
    """Rapport d'aspect réduit sous forme ``"a:b"`` (ex. 1600×900 → ``"16:9"``)."""
    width, height = int(width), int(height)
    divisor = gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


def render_preview(
    genome: ArtworkGenome,
    max_side: int = DEFAULT_MAX_SIDE,
    engine: Engine | None = None,
    point_cap: int | None = None,
) -> Image.Image:
    """Rend un aperçu réduit du génome (sans muter l'original).

    Le génome d'origine est préservé : on rend une copie redimensionnée. Si
    ``point_cap`` est fourni, le nombre de points de chaque couche y est plafonné
    pour un aperçu plus rapide (mode brouillon) — la copie est alors profonde pour
    ne pas altérer les couches d'origine.
    """
    width, height = preview_dimensions(genome.width, genome.height, max_side)
    if point_cap is None:
        small = replace(genome, width=width, height=height)  # couches partagées (lecture seule)
    else:
        small = copy.deepcopy(genome)
        small.width, small.height = width, height
        for layer in small.layers:
            layer.n_points = min(layer.n_points, point_cap)
    engine = engine or Engine()
    return engine.render(small, tile="off")
