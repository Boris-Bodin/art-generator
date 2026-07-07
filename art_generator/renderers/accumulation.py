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


def _point_modulation(
    points: np.ndarray, layer: LayerGenome
) -> tuple[np.ndarray, np.ndarray]:
    """Poids lumineux et rayon d'épaisseur par point, pilotés par bruit (Phase 2+).

    Retourne ``(weight, radius)`` alignés sur ``points`` :
      * ``weight`` module la contribution lumineuse de chaque point ;
      * ``radius`` (rayon pixel entier) module localement l'épaisseur du trait.
    """
    n = len(points)
    base_radius = max(0, int(round(layer.thickness)) - 1)
    weight = np.ones(n, dtype=np.float64)
    radius = np.full(n, base_radius, dtype=np.int64)

    if layer.noise_type == "none" or (
        layer.light_noise <= 0 and layer.thickness_noise <= 0
    ):
        return weight, radius

    fx = points[:, 0] * layer.warp_freq
    fy = points[:, 1] * layer.warp_freq
    u = 0.5 * (noise.sample(layer.noise_type, fx + 5.3, fy + 9.1, layer.noise_seed + 555) + 1.0)

    if layer.light_noise > 0:
        weight = np.clip(1.0 - layer.light_noise + 2.0 * layer.light_noise * u, 0.05, 4.0)
    if layer.thickness_noise > 0:
        r = np.round(layer.thickness + layer.thickness_noise * u).astype(np.int64) - 1
        radius = np.clip(r, 0, _MAX_RADIUS)
    return weight, radius


def _apply_noise(
    points: np.ndarray, values: np.ndarray, layer: LayerGenome
) -> tuple[np.ndarray, np.ndarray]:
    """Déforme le domaine (warp) et/ou module les valeurs de coloration par bruit.

    Le bruit est échantillonné aux positions des points (mises à l'échelle par
    ``warp_freq``) ; deux seeds décorrélées donnent des déplacements ``x``/``y``
    indépendants. Reproductible via ``layer.noise_seed``.
    """
    kind = layer.noise_type
    fx = points[:, 0] * layer.warp_freq
    fy = points[:, 1] * layer.warp_freq

    if layer.warp > 0:
        nx = noise.sample(kind, fx, fy, layer.noise_seed)
        ny = noise.sample(kind, fx + 37.1, fy + 17.9, layer.noise_seed + 7919)
        points = points + layer.warp * np.column_stack((nx, ny))

    if layer.color_noise > 0:
        nc = noise.sample(kind, fx * 0.5, fy * 0.5, layer.noise_seed + 104729)
        values = np.clip(values + layer.color_noise * nc, 0.0, 1.0)

    return points, values


def render_layer(
    equation: Equation, layer: LayerGenome, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Rend une couche et renvoie ``(color, alpha)`` (Phase 4).

    * ``color`` ``(H, W, 3)`` — couleur *non prémultipliée* de la couche ;
    * ``alpha`` ``(H, W)`` — couverture dans ``[0, 1]`` dérivée de la densité.

    La composition sur le fond (par cet alpha) est déléguée à
    :func:`art_generator.core.blend.composite`, ce qui découple la forme du fond :
    les zones vides (``alpha = 0``) laissent transparaître le fond.
    """
    zero = (
        np.zeros((height, width, 3), dtype=np.float64),
        np.zeros((height, width), dtype=np.float64),
    )
    points, values = equation.sample(layer.n_points)
    points, values = clean_points(points, values)
    if len(points) == 0:
        return zero

    # Centrage robuste avant symétrie (rotations/miroirs corrects).
    center = np.median(points, axis=0)
    points = points - center
    points, values = apply_symmetry(points, values, layer.symmetry, layer.symmetry_order)

    # Déformation du domaine et/ou modulation couleur par bruit (Phase 2).
    if layer.noise_type != "none":
        points, values = _apply_noise(points, values, layer)

    weight, radius = _point_modulation(points, layer)

    coords, inside = fit_to_canvas(points, width, height, center_on=layer.framing)
    if len(coords) == 0:
        return zero
    values = values[inside]
    weight = weight[inside]
    radius = radius[inside]

    colors = procedural.apply(values, layer.palette) * weight[:, None]  # (M, 3)

    acc_col = np.zeros((height, width, 3), dtype=np.float64)
    acc_w = np.zeros((height, width), dtype=np.float64)

    xs, ys = coords[:, 0], coords[:, 1]
    r2 = radius * radius
    for dx, dy, d2 in _disk_offsets(int(radius.max())):
        nx = xs + dx
        ny = ys + dy
        # dans le cadre ET le point est assez épais pour couvrir cet offset
        m = (nx >= 0) & (nx < width) & (ny >= 0) & (ny < height) & (r2 >= d2)
        np.add.at(acc_col, (ny[m], nx[m]), colors[m])
        np.add.at(acc_w, (ny[m], nx[m]), weight[m])

    return _resolve(acc_col, acc_w, layer)


def _blur(a: np.ndarray, radius: int = 6) -> np.ndarray:
    """Flou gaussien d'un tampon flottant ``[0, 1]`` via PIL (mono ou RVB)."""
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), np.float64) / 255.0


def _resolve(
    acc_col: np.ndarray, acc_w: np.ndarray, layer: LayerGenome
) -> tuple[np.ndarray, np.ndarray]:
    """Compression tonale HDR + halo → ``(color, alpha)`` (Phase 4).

    La luminance compressée sert de **couverture** (``alpha``) : dense = opaque,
    vide = transparent. La couleur renvoyée est *non prémultipliée* (``avg_col``),
    de sorte que ``color * alpha`` reproduit exactement l'ancien tampon additif —
    le rendu sur fond noir reste identique au pixel près.
    """
    eps = 1e-9
    # Teinte moyenne par pixel.
    avg_col = acc_col / np.maximum(acc_w[..., None], eps)

    # Luminance compressée logarithmiquement puis normalisée par percentile.
    bright = np.log1p(acc_w * layer.exposure)
    positive = bright[bright > 0]
    if positive.size:
        hi = np.percentile(positive, 98.0)
        if hi > eps:
            bright = np.clip(bright / hi, 0.0, 1.0)
    bright = np.power(bright, 0.65)  # relèvement des tons sombres

    premult = avg_col * bright[..., None]  # couleur prémultipliée (= ancien layer_rgb)
    alpha = bright

    if layer.glow > 0:
        # Le halo enrichit couleur *et* couverture, de façon cohérente.
        premult = premult + layer.glow * _blur(premult)
        alpha = alpha + layer.glow * _blur(alpha)

    alpha = np.clip(alpha, 0.0, 1.0)
    # Dé-prémultiplication : color * alpha == premult (couverture non écrêtée à 0).
    color = premult / np.maximum(alpha[..., None], eps)
    return color, alpha
