"""Renderer par accumulation lumineuse (« light painting »).

Chaque point est projeté dans un tampon HDR : on cumule la couleur pondérée et
la densité, puis on applique une compression tonale logarithmique et un halo
(glow) par flou gaussien. Ce rendu additif donne à toutes les familles
d'équations une même signature lumineuse.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from ..core.genome import LayerGenome
from ..equations.base import Equation
from ..noise import fields as noise
from ..palettes import procedural
from ..utils.math_utils import clean_points, fit_to_canvas
from .symmetry import apply_symmetry


_MAX_RADIUS = 6  # borne l'épaisseur (et donc le coût de l'accumulation)

# Familles dont la forme est **filamentaire** (courbes/lignes 1D) : leur couverture
# n'est pas conservée par la seule densité de points quand on monte en résolution
# (des traits de 1 px absolu couvrent relativement moins d'aire). On y met donc
# l'épaisseur *et* le glow à l'échelle de la résolution pour garder un voile de
# densité constante. Les familles « nuage » (attractor, particles, fractal)
# remplissent une aire 2D : leur densité suffit, on garde des points fins et nets.
_STROKE_SCALE_FAMILIES = frozenset({"vector_field", "parametric", "polar", "complex"})

# Familles au support **strictement 1D** (un réseau de lignes de courant, pas un
# voile qui remplit une aire) : leur densité par pixel se conserve en faisant
# croître le nombre de points **linéairement** (``scale``), pas avec l'aire — sans
# quoi les lignes deviennent trop denses (centre trop sombre) en HD. Les autres
# familles remplissent une aire 2D et suivent l'aire (``scale**2``).
_LINEAR_POINT_FAMILIES = frozenset({"vector_field"})


def _stroke_scale(family: str, scale: float) -> float:
    """Facteur d'échelle des traits (épaisseur/glow) selon la famille."""
    return scale if family in _STROKE_SCALE_FAMILIES else 1.0


def _point_factor(family: str, scale: float) -> float:
    """Facteur multiplicatif du nombre de points selon la résolution et la famille.

    ``scale`` (linéaire) pour les supports 1D purs (:data:`_LINEAR_POINT_FAMILIES`),
    ``scale**2`` (aire) sinon — de sorte que la densité par pixel reste constante
    dans les deux cas. Ce facteur pilote aussi la réduction de ``dt`` des familles
    à trajectoires (voir ``engine._build_equation``), pour préserver la forme.
    """
    if scale == 1.0:
        return 1.0
    return scale if family in _LINEAR_POINT_FAMILIES else scale * scale


def _point_count(family: str, n_points: int, scale: float) -> int:
    """Nombre de points à échantillonner pour une couche (voir :func:`_point_factor`)."""
    return int(round(n_points * _point_factor(family, scale)))


def _disk_offsets(radius: int) -> list[tuple[int, int, int]]:
    """Offsets ``(dx, dy, dist2)`` d'un disque de rayon pixel ``radius``."""
    if radius <= 0:
        return [(0, 0, 0)]
    offsets = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d2 = dx * dx + dy * dy
            if d2 <= radius * radius:
                offsets.append((dx, dy, d2))
    return offsets


def _disk_area(radius: int) -> int:
    """Nombre de pixels d'un disque de rayon ``radius`` (au moins 1)."""
    return len(_disk_offsets(int(radius)))


def _noise_field(
    layer: LayerGenome, x: np.ndarray, y: np.ndarray, seed: int
) -> np.ndarray:
    """Échantillonne le bruit de la couche, en 2D ou en 3D selon ``noise_3d``.

    ``noise_3d`` faux (défaut) ⇒ bruit 2D historique (``noise_z`` ignoré, rendu
    inchangé au pixel près). Vrai ⇒ bruit 3D avec ``noise_z`` en 3e coordonnée
    (axe temporel), pour un flux cohérent quand une piste anime ``noise_z``.
    """
    if layer.noise_3d:
        z = np.full_like(x, layer.noise_z)
        return noise.sample3d(layer.noise_type, x, y, z, seed)
    return noise.sample(layer.noise_type, x, y, seed)


def _point_modulation(
    points: np.ndarray, layer: LayerGenome, stroke_scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Poids lumineux et rayon d'épaisseur par point, pilotés par bruit.

    Retourne ``(weight, radius)`` alignés sur ``points`` :
      * ``weight`` module la contribution lumineuse de chaque point ;
      * ``radius`` (rayon pixel entier) module localement l'épaisseur du trait.

    ``stroke_scale`` épaissit les traits proportionnellement à la
    résolution pour les familles filamentaires (voir :func:`_stroke_scale`) ;
    il vaut 1 pour les familles nuage (traits fins et nets). Le poids est alors
    **normalisé par l'aire du disque** (facteur ``aire(rayon réf)/aire(rayon
    courant)``) : élargir le trait le *répartit* sans l'éclaircir/assombrir
    davantage, pour que la densité visuelle reste celle de la référence. À
    ``stroke_scale == 1`` le facteur vaut 1 : calcul identique à l'historique.
    """
    n = len(points)
    max_radius = int(round(_MAX_RADIUS * stroke_scale))
    base_radius = max(0, int(round(layer.thickness * stroke_scale)) - 1)
    # Normalisation d'aire : rapport entre le disque à stroke_scale=1 et le disque
    # élargi. Vaut 1 quand stroke_scale=1 (rayons égaux) -> invariant préservé.
    ref_radius = max(0, int(round(layer.thickness)) - 1)
    area_norm = _disk_area(ref_radius) / _disk_area(base_radius)
    weight = np.full(n, area_norm, dtype=np.float64)
    radius = np.full(n, base_radius, dtype=np.int64)

    if layer.noise_type == "none" or (
        layer.light_noise <= 0 and layer.thickness_noise <= 0
    ):
        return weight, radius

    fx = points[:, 0] * layer.warp_freq
    fy = points[:, 1] * layer.warp_freq
    u = 0.5 * (_noise_field(layer, fx + 5.3, fy + 9.1, layer.noise_seed + 555) + 1.0)

    if layer.light_noise > 0:
        weight = area_norm * np.clip(1.0 - layer.light_noise + 2.0 * layer.light_noise * u, 0.05, 4.0)
    if layer.thickness_noise > 0:
        r = np.round((layer.thickness + layer.thickness_noise * u) * stroke_scale).astype(np.int64) - 1
        radius = np.clip(r, 0, max_radius)
    return weight, radius


def _apply_noise(
    points: np.ndarray, values: np.ndarray, layer: LayerGenome
) -> tuple[np.ndarray, np.ndarray]:
    """Déforme le domaine (warp) et/ou module les valeurs de coloration par bruit.

    Le bruit est échantillonné aux positions des points (mises à l'échelle par
    ``warp_freq``) ; deux seeds décorrélées donnent des déplacements ``x``/``y``
    indépendants. Reproductible via ``layer.noise_seed``.
    """
    fx = points[:, 0] * layer.warp_freq
    fy = points[:, 1] * layer.warp_freq

    if layer.warp > 0:
        nx = _noise_field(layer, fx, fy, layer.noise_seed)
        ny = _noise_field(layer, fx + 37.1, fy + 17.9, layer.noise_seed + 7919)
        points = points + layer.warp * np.column_stack((nx, ny))

    if layer.color_noise > 0:
        nc = _noise_field(layer, fx * 0.5, fy * 0.5, layer.noise_seed + 104729)
        values = np.clip(values + layer.color_noise * nc, 0.0, 1.0)

    return points, values


def project_layer(
    equation: Equation, layer: LayerGenome, width: int, height: int, scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Déroule le pipeline d'une couche jusqu'au *nuage de points projeté*.

    C'est le tronc commun réutilisé par le rendu simple, le rendu par tuiles
    et l'export vectoriel : échantillonnage → nettoyage → centrage →
    symétrie → bruit → modulation → cadrage → couleur.

    ``scale`` (facteur linéaire de résolution) rend le rendu
    *indépendant de la résolution* : le nombre de points croît pour garder la
    densité par pixel constante — avec l'aire, ou linéairement pour les supports
    1D purs (:func:`_point_count`). Les familles filamentaires épaississent en plus
    traits et glow (:func:`_stroke_scale`) ; les familles nuage gardent des traits
    fins et nets. À ``scale == 1`` le résultat est identique à l'historique.

    Returns:
        ``(coords, colors, weight, radius)`` alignés (longueur ``M``) :

        * ``coords`` ``(M, 2)`` — coordonnées pixel entières ``(x, y)`` dans le cadre ;
        * ``colors`` ``(M, 3)`` — couleur *pondérée par la lumière* de chaque point ;
        * ``weight`` ``(M,)`` — poids lumineux (densité) de chaque point ;
        * ``radius`` ``(M,)`` — rayon pixel d'épaisseur de chaque point.

        Le nuage peut être vide (``M == 0``).
    """
    empty = (
        np.empty((0, 2), dtype=np.int64),
        np.empty((0, 3), dtype=np.float64),
        np.empty(0, dtype=np.float64),
        np.empty(0, dtype=np.int64),
    )
    n_points = _point_count(layer.equation_family, layer.n_points, scale)
    points, values = equation.sample(n_points)
    points, values = clean_points(points, values)
    if len(points) == 0:
        return empty

    # Source de couleur = longueur d'arc cumulée : calculée sur l'orbite unique,
    # avant la symétrie (qui réplique les valeurs) pour que chaque copie garde un
    # dégradé 0→1 propre plutôt qu'un saut entre copies.
    if layer.color_source == "arc":
        values = Equation.arc_length_values(points)

    # Centrage robuste avant symétrie (rotations/miroirs corrects).
    center = np.median(points, axis=0)
    points = points - center
    points, values = apply_symmetry(points, values, layer.symmetry, layer.symmetry_order)

    # Déformation du domaine et/ou modulation couleur par bruit.
    if layer.noise_type != "none":
        points, values = _apply_noise(points, values, layer)

    weight, radius = _point_modulation(points, layer, _stroke_scale(layer.equation_family, scale))

    coords, inside = fit_to_canvas(points, width, height, center_on=layer.framing)
    if len(coords) == 0:
        return empty
    values = values[inside]
    weight = weight[inside]
    radius = radius[inside]

    colors = procedural.apply(values, layer.palette) * weight[:, None]  # (M, 3)
    return coords, colors, weight, radius


def accumulate(
    coords: np.ndarray,
    colors: np.ndarray | None,
    weight: np.ndarray,
    radius: np.ndarray,
    width: int,
    y0: int,
    y1: int,
) -> tuple[np.ndarray | None, np.ndarray]:
    """Rasterise le nuage projeté dans la bande de lignes ``[y0, y1)``.

    Le disque d'épaisseur de chaque point est éclaté par ``np.add.at``. Passer
    ``y0=0, y1=height`` rasterise l'image entière (chemin simple) ; une bande
    plus étroite ne matérialise qu'une portion, ce qui borne la mémoire pour les
    très grandes résolutions (rendu par tuiles).

    Si ``colors`` est ``None``, seule la densité ``acc_w`` est cumulée (pré-passe
    de normalisation) — ``acc_col`` renvoyé vaut alors ``None``.

    L'éclatement se fait via :func:`numpy.bincount` sur un index de pixel aplati
    (nettement plus rapide que ``numpy.ufunc.at``, non bufferisé) ; l'ordre de
    parcours (offset par offset) est préservé, si bien que le chemin simple et le
    rendu par tuiles restent **identiques au pixel près**.
    """
    band_h = y1 - y0
    acc_col = None if colors is None else np.zeros((band_h, width, 3), dtype=np.float64)
    acc_w = np.zeros((band_h, width), dtype=np.float64)
    if len(coords) == 0:
        return acc_col, acc_w

    xs = coords[:, 0]
    ys = coords[:, 1] - y0
    r2 = radius * radius
    minlength = band_h * width
    acc_w_flat = acc_w.reshape(-1)
    acc_col_flat = None if acc_col is None else acc_col.reshape(-1, 3)
    for dx, dy, d2 in _disk_offsets(int(radius.max())):
        nx = xs + dx
        ny = ys + dy
        # dans le cadre ET le point est assez épais pour couvrir cet offset
        m = (nx >= 0) & (nx < width) & (ny >= 0) & (ny < band_h) & (r2 >= d2)
        # ``intp`` = index natif de la plateforme : int64 sur desktop (rendu
        # inchangé), int32 sous Pyodide/WASM — où ``np.bincount`` refuse un index
        # int64 (cast « safe » impossible). Les indices restent < 2^31 pour toute
        # résolution réaliste, la conversion est donc sûre.
        flat = (ny[m] * width + nx[m]).astype(np.intp)
        acc_w_flat += np.bincount(flat, weights=weight[m], minlength=minlength)
        if acc_col_flat is not None:
            cm = colors[m]
            for c in range(3):
                acc_col_flat[:, c] += np.bincount(flat, weights=cm[:, c], minlength=minlength)

    return acc_col, acc_w


def render_layer(
    equation: Equation, layer: LayerGenome, width: int, height: int, scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Rend une couche et renvoie ``(color, alpha)``.

    * ``color`` ``(H, W, 3)`` — couleur *non prémultipliée* de la couche ;
    * ``alpha`` ``(H, W)`` — couverture dans ``[0, 1]`` dérivée de la densité.

    La composition sur le fond (par cet alpha) est déléguée à
    :func:`art_generator.core.blend.composite`, ce qui découple la forme du fond :
    les zones vides (``alpha = 0``) laissent transparaître le fond.

    ``scale`` : facteur d'indépendance à la résolution (voir :func:`project_layer`).
    """
    coords, colors, weight, radius = project_layer(equation, layer, width, height, scale)
    if len(coords) == 0:
        return (
            np.zeros((height, width, 3), dtype=np.float64),
            np.zeros((height, width), dtype=np.float64),
        )
    acc_col, acc_w = accumulate(coords, colors, weight, radius, width, 0, height)
    return _resolve(acc_col, acc_w, layer, scale=_stroke_scale(layer.equation_family, scale))


def _blur(a: np.ndarray, radius: int = 6) -> np.ndarray:
    """Flou gaussien d'un tampon flottant ``[0, 1]`` via PIL (mono ou RVB)."""
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), np.float64) / 255.0


_AUTO = object()  # sentinelle : « calcule le percentile localement » (chemin simple)


def global_hi(acc_w: np.ndarray, layer: LayerGenome) -> float | None:
    """Percentile de normalisation (98e) de la luminance compressée d'une couche.

    Calculé une fois sur la densité **globale** pour que le rendu par tuiles
    normalise chaque bande à l'identique du chemin simple. Renvoie ``None`` quand
    aucune normalisation ne s'applique (couche vide ou percentile négligeable).
    """
    eps = 1e-9
    bright = np.log1p(acc_w * layer.exposure)
    positive = bright[bright > 0]
    if positive.size:
        hi = float(np.percentile(positive, 98.0))
        return hi if hi > eps else None
    return None


def _resolve(
    acc_col: np.ndarray,
    acc_w: np.ndarray,
    layer: LayerGenome,
    hi: object = _AUTO,
    scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compression tonale HDR + halo → ``(color, alpha)``.

    La luminance compressée sert de **couverture** (``alpha``) : dense = opaque,
    vide = transparent. La couleur renvoyée est *non prémultipliée* (``avg_col``),
    de sorte que ``color * alpha`` reproduit exactement l'ancien tampon additif —
    le rendu sur fond noir reste identique au pixel près.

    ``hi`` : percentile de normalisation. Par défaut (``_AUTO``) il est calculé
    localement sur ``acc_w`` (chemin simple, comportement historique) ; le rendu
    par tuiles passe le ``hi`` **global** de la couche pour que chaque bande soit
    normalisée de façon cohérente (voir :func:`global_hi`).

    ``scale`` : facteur de trait élargissant le rayon du halo (glow)
    proportionnellement pour les familles filamentaires. À ``scale == 1`` le rayon
    vaut 6 px (identique à l'historique).
    """
    eps = 1e-9
    blur_radius = max(1, int(round(6 * scale)))
    # Teinte moyenne par pixel.
    avg_col = acc_col / np.maximum(acc_w[..., None], eps)

    # Luminance compressée logarithmiquement puis normalisée par percentile.
    bright = np.log1p(acc_w * layer.exposure)
    if hi is _AUTO:
        positive = bright[bright > 0]
        hi = float(np.percentile(positive, 98.0)) if positive.size else None
    if hi is not None and hi > eps:
        bright = np.clip(bright / hi, 0.0, 1.0)
    bright = np.power(bright, 0.65)  # relèvement des tons sombres

    premult = avg_col * bright[..., None]  # couleur prémultipliée (= ancien layer_rgb)
    alpha = bright

    if layer.glow > 0:
        # Le halo enrichit couleur *et* couverture, de façon cohérente.
        premult = premult + layer.glow * _blur(premult, blur_radius)
        alpha = alpha + layer.glow * _blur(alpha, blur_radius)

    alpha = np.clip(alpha, 0.0, 1.0)
    # Dé-prémultiplication : color * alpha == premult (couverture non écrêtée à 0).
    color = premult / np.maximum(alpha[..., None], eps)
    return color, alpha
