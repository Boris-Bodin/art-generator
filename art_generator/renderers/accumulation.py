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


def _kernel_offsets(thickness: float) -> list[tuple[int, int]]:
    """Petit disque d'offsets pixel selon l'épaisseur demandée."""
    radius = max(0, int(round(thickness)) - 1)
    if radius == 0:
        return [(0, 0)]
    offsets = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                offsets.append((dx, dy))
    return offsets


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
) -> np.ndarray:
    """Rend une couche complète et renvoie un tampon ``(H, W, 3)`` dans ``[0, 1]``."""
    points, values = equation.sample(layer.n_points)
    points, values = clean_points(points, values)
    if len(points) == 0:
        return np.zeros((height, width, 3), dtype=np.float64)

    # Centrage robuste avant symétrie (rotations/miroirs corrects).
    center = np.median(points, axis=0)
    points = points - center
    points, values = apply_symmetry(points, values, layer.symmetry, layer.symmetry_order)

    # Déformation du domaine et/ou modulation couleur par bruit (Phase 2).
    if layer.noise_type != "none":
        points, values = _apply_noise(points, values, layer)

    coords, inside = fit_to_canvas(points, width, height)
    if len(coords) == 0:
        return np.zeros((height, width, 3), dtype=np.float64)
    values = values[inside]

    colors = procedural.apply(values, layer.palette)  # (M, 3)

    acc_col = np.zeros((height, width, 3), dtype=np.float64)
    acc_w = np.zeros((height, width), dtype=np.float64)

    xs, ys = coords[:, 0], coords[:, 1]
    for dx, dy in _kernel_offsets(layer.thickness):
        nx = xs + dx
        ny = ys + dy
        m = (nx >= 0) & (nx < width) & (ny >= 0) & (ny < height)
        np.add.at(acc_col, (ny[m], nx[m]), colors[m])
        np.add.at(acc_w, (ny[m], nx[m]), 1.0)

    return _tonemap(acc_col, acc_w, layer)


def _tonemap(acc_col: np.ndarray, acc_w: np.ndarray, layer: LayerGenome) -> np.ndarray:
    """Compression tonale HDR + halo."""
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

    layer_rgb = avg_col * bright[..., None]

    if layer.glow > 0:
        img = Image.fromarray((np.clip(layer_rgb, 0, 1) * 255).astype(np.uint8))
        blurred = np.asarray(
            img.filter(ImageFilter.GaussianBlur(radius=6)), dtype=np.float64
        ) / 255.0
        layer_rgb = layer_rgb + layer.glow * blurred

    return np.clip(layer_rgb, 0.0, 1.0)
