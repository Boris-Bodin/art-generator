"""Export vectoriel SVG/PDF « par tracés ».

Le rendu matriciel est un *light painting* additif d'un million de points, dont
le glow HDR ne se transpose pas fidèlement en géométrie vectorielle. L'export
vectoriel est donc une **esthétique distincte** : chaque point du nuage projeté
devient un petit disque coloré (stipple), fidèle au modèle « nuage de points »
mais rendu en tracés redimensionnables à l'infini.

On s'appuie sur matplotlib (déjà une dépendance) : un même code produit SVG *et*
PDF, le format découlant de l'extension du fichier, sans binaire natif.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # rendu hors-écran ; savefig choisit le writer SVG/PDF
import numpy as np
from matplotlib.figure import Figure

from ..core.genome import ArtworkGenome
from ..core.rng import RNG
from ..equations import registry
from ..renderers import accumulation

# Nombre de points tracés par couche (borne la taille du fichier vectoriel).
_DEFAULT_MAX_POINTS = 50_000


def _background_color(genome: ArtworkGenome) -> tuple[float, float, float]:
    """Couleur de fond *unie* représentative (le vectoriel n'imprime pas de dégradé)."""
    kind = genome.background
    params = genome.background_params or {}
    if kind == "black":
        return (0.0, 0.0, 0.0)
    if kind == "white":
        return (1.0, 1.0, 1.0)
    if kind == "gradient":
        top = np.asarray(params.get("top", (0.02, 0.02, 0.06)), dtype=float)
        bottom = np.asarray(params.get("bottom", (0.0, 0.0, 0.0)), dtype=float)
        return tuple((top + bottom) / 2.0)
    if kind == "radial":
        return tuple(np.asarray(params.get("inner", (0.06, 0.06, 0.12)), dtype=float))
    return (0.0, 0.0, 0.0)


def _subsample(n: int, cap: int, seed: int) -> np.ndarray:
    """Indices d'un sous-échantillon déterministe (≤ ``cap``) parmi ``n`` points."""
    if n <= cap:
        return np.arange(n)
    return np.sort(RNG(seed).generator.choice(n, size=cap, replace=False))


def save_vector(
    genome: ArtworkGenome,
    path: str | Path,
    dpi: int = 300,
    max_points: int = _DEFAULT_MAX_POINTS,
    point_alpha: float = 0.55,
    point_size: float = 1.4,
) -> Path:
    """Exporte le génome en SVG ou PDF vectoriel (par tracés).

    Args:
        path: destination ; ``.svg`` ou ``.pdf`` (le format en découle).
        dpi: résolution nominale (dimensionne la figure ; le tracé reste vectoriel).
        max_points: plafond de points tracés par couche (taille du fichier).
        point_alpha: opacité de chaque disque (le recouvrement crée la densité).
        point_size: diamètre visé d'un point, en pixels de la toile nominale.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    w, h = genome.width, genome.height
    bg = _background_color(genome)

    fig = Figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_facecolor(bg)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_axis_off()
    ax.set_xlim(0.0, w)
    ax.set_ylim(h, 0.0)  # origine en haut à gauche, comme l'image matricielle
    ax.set_facecolor(bg)

    # Diamètre point (px toile) → aire de marqueur en points² (matplotlib).
    pts_per_px = 72.0 / dpi
    marker_area = max((point_size * pts_per_px) ** 2, 1e-4)

    for i, layer in enumerate(genome.layers):
        equation = registry.build(layer.equation_family, layer.equation_params)
        coords, colors, _weight, _radius = accumulation.project_layer(equation, layer, w, h)
        if len(coords) == 0:
            continue
        idx = _subsample(len(coords), max_points, genome.seed + i)
        xy = coords[idx]
        rgb = np.clip(colors[idx], 0.0, 1.0)
        ax.scatter(
            xy[:, 0], xy[:, 1], s=marker_area, c=rgb, alpha=point_alpha,
            linewidths=0.0, marker="o", edgecolors="none",
        )

    fig.savefig(path, dpi=dpi, facecolor=bg)
    return path
