"""Champs de bruit procédural, vectorisés et déterministes.

Tous les bruits sont pilotés par une seed entière et évalués en une passe NumPy
sur des tableaux de coordonnées. Ils servent à déformer le domaine (warp) des
points, à moduler les couleurs, l'épaisseur ou la lumière.

Fournis :
  * ``perlin2d`` — bruit de gradient de Perlin, sortie ~``[-1, 1]``
  * ``fbm``      — somme fractale d'octaves de Perlin (fractal Brownian motion)
  * ``worley2d`` — bruit cellulaire (distance au point de caractéristique F1)
"""

from __future__ import annotations

import numpy as np

_GRAD2 = np.array(
    [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]],
    dtype=np.float64,
)


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + t * (b - a)


def perlin2d(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Bruit de Perlin 2D vectorisé. Résultat dans ~``[-1, 1]``."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(256).astype(np.int64)
    perm = np.concatenate((perm, perm))

    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf = x - xi
    yf = y - yi
    xi &= 255
    yi &= 255
    u = _fade(xf)
    v = _fade(yf)

    def grad(ix, iy, dx, dy):
        idx = perm[(perm[ix & 255] + (iy & 255)) & 255] & 7
        g = _GRAD2[idx]
        return g[..., 0] * dx + g[..., 1] * dy

    n00 = grad(xi, yi, xf, yf)
    n10 = grad(xi + 1, yi, xf - 1, yf)
    n01 = grad(xi, yi + 1, xf, yf - 1)
    n11 = grad(xi + 1, yi + 1, xf - 1, yf - 1)

    x1 = _lerp(n00, n10, u)
    x2 = _lerp(n01, n11, u)
    return _lerp(x1, x2, v)


def fbm(
    x: np.ndarray, y: np.ndarray, seed: int, octaves: int = 5, lacunarity: float = 2.0,
    gain: float = 0.5,
) -> np.ndarray:
    """Somme fractale d'octaves de Perlin. Résultat renormalisé dans ~``[-1, 1]``."""
    total = np.zeros_like(x)
    freq, amp, norm = 1.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * perlin2d(x * freq, y * freq, seed + o * 101)
        norm += amp
        freq *= lacunarity
        amp *= gain
    return total / max(norm, 1e-9)


def _hash01(ix: np.ndarray, iy: np.ndarray, seed: int, salt: int) -> np.ndarray:
    """Hachage entier déterministe des coordonnées de cellule vers ``[0, 1)``."""
    h = (ix * 374761393 + iy * 668265263 + seed * 2246822519 + salt * 3266489917)
    h = (h ^ (h >> np.int64(13))) * 1274126177
    h = h ^ (h >> np.int64(16))
    return (h & 0xFFFFFF).astype(np.float64) / float(0x1000000)


def worley2d(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Bruit cellulaire de Worley (distance F1 au point le plus proche).

    Un point de caractéristique est placé, jitté, dans chaque cellule entière.
    Pour chaque requête on cherche le plus proche parmi les 9 cellules voisines.
    Résultat normalisé dans ~``[0, 1]``.
    """
    cx = np.floor(x).astype(np.int64)
    cy = np.floor(y).astype(np.int64)
    best = np.full(x.shape, np.inf)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx = cx + dx
            ny = cy + dy
            fx = nx + _hash01(nx, ny, seed, 1)
            fy = ny + _hash01(nx, ny, seed, 2)
            dist = (x - fx) ** 2 + (y - fy) ** 2
            best = np.minimum(best, dist)
    return np.clip(np.sqrt(best), 0.0, 1.0)


_F2 = 0.5 * (np.sqrt(3.0) - 1.0)
_G2 = (3.0 - np.sqrt(3.0)) / 6.0
_GRAD12 = np.array(
    [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0],
     [1, 0], [-1, 0], [0, 1], [0, -1], [0, 1], [0, -1]],
    dtype=np.float64,
)


def simplex2d(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Bruit Simplex 2D (Perlin/Gustavson), vectorisé. Résultat dans ~``[-1, 1]``.

    Contrairement au Perlin sur grille carrée, le Simplex échantillonne une grille
    de triangles : moins d'artefacts directionnels, gradient continu, coût moindre
    en dimensions supérieures.
    """
    rng = np.random.default_rng(seed)
    perm = rng.permutation(256).astype(np.int64)
    perm = np.concatenate((perm, perm))  # longueur 512, évite les modulos
    perm_mod12 = perm % 12

    s = (x + y) * _F2
    i = np.floor(x + s).astype(np.int64)
    j = np.floor(y + s).astype(np.int64)
    t = (i + j) * _G2
    x0 = x - (i - t)
    y0 = y - (j - t)

    upper = x0 > y0
    i1 = np.where(upper, 1, 0)
    j1 = np.where(upper, 0, 1)

    x1 = x0 - i1 + _G2
    y1 = y0 - j1 + _G2
    x2 = x0 - 1.0 + 2.0 * _G2
    y2 = y0 - 1.0 + 2.0 * _G2

    ii = i & 255
    jj = j & 255
    gi0 = perm_mod12[ii + perm[jj]]
    gi1 = perm_mod12[ii + i1 + perm[jj + j1]]
    gi2 = perm_mod12[ii + 1 + perm[jj + 1]]

    def _corner(gi, xx, yy):
        tt = 0.5 - xx * xx - yy * yy
        g = _GRAD12[gi]
        return np.where(tt < 0, 0.0, (tt ** 4) * (g[..., 0] * xx + g[..., 1] * yy))

    total = _corner(gi0, x0, y0) + _corner(gi1, x1, y1) + _corner(gi2, x2, y2)
    return 70.0 * total


def sample(kind: str, x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Dispatch générique. Sortie normalisée dans ~``[-1, 1]`` pour tous les types."""
    if kind == "perlin":
        return perlin2d(x, y, seed)
    if kind == "simplex":
        return simplex2d(x, y, seed)
    if kind == "fbm":
        return fbm(x, y, seed)
    if kind == "worley":
        return worley2d(x, y, seed) * 2.0 - 1.0
    raise ValueError(f"Type de bruit inconnu : {kind!r}")
