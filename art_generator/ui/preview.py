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
from math import ceil

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


def rescale_offset(offset: float, cursor: float, old_scale: float, new_scale: float) -> float:
    """Nouveau décalage d'affichage d'un axe pour un zoom **centré sur le curseur**.

    Le point de l'image sous ``cursor`` (en pixels canevas) doit y rester après le
    passage de l'échelle ``old_scale`` à ``new_scale``. L'image est dessinée à
    partir de ``offset`` : le point image sous le curseur vaut ``(cursor-offset)/
    old_scale`` ; on résout le nouvel ``offset`` qui le laisse fixe.
    """
    return cursor - (cursor - offset) * new_scale / old_scale


def visible_source_box(
    img_w: int, img_h: int, canvas_w: int, canvas_h: int, scale: float,
    offset: tuple[float, float],
) -> tuple[int, int, int, int]:
    """Boîte source (px image) réellement visible dans le canevas au zoom courant.

    Permet de ne redimensionner que la portion affichée : borne la taille de
    l'image intermédiaire à ~celle du canevas, quel que soit le facteur de zoom.
    Renvoie ``(x0, y0, x1, y1)`` avec ``x0<x1`` et ``y0<y1`` tant qu'une partie de
    l'image est visible.
    """
    ox, oy = offset
    x0 = max(0, int((0 - ox) / scale))
    y0 = max(0, int((0 - oy) / scale))
    x1 = min(img_w, int(ceil((canvas_w - ox) / scale)))
    y1 = min(img_h, int(ceil((canvas_h - oy) / scale)))
    return x0, y0, x1, y1


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
