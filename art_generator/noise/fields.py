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

from functools import lru_cache

import numpy as np

_GRAD2 = np.array(
    [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]],
    dtype=np.float64,
)


@lru_cache(maxsize=256)
def _permutation(seed: int) -> np.ndarray:
    """Table de permutation (longueur 512) mémoïsée par seed.

    La table ne dépend que de la seed ; la recalculer à chaque appel de bruit
    (jusqu'à ``octaves`` fois par ``fbm``, à chaque pas de la turbulence des
    particules) est du gaspillage. Le cache renvoie **le même tableau** pour une
    seed donnée : résultat identique au pixel près. Le tableau est traité comme
    immuable (jamais modifié en place par les appelants).
    """
    rng = np.random.default_rng(seed)
    perm = rng.permutation(256).astype(np.int64)
    return np.concatenate((perm, perm))


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + t * (b - a)


def perlin2d(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Bruit de Perlin 2D vectorisé. Résultat dans ~``[-1, 1]``."""
    perm = _permutation(seed)

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
        # Indexation directe des composantes : évite le tableau (N, 2) temporaire.
        return _GRAD2[idx, 0] * dx + _GRAD2[idx, 1] * dy

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
    perm = _permutation(seed)  # longueur 512, évite les modulos
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


# --- bruits 3D (la 3e coordonnée sert d'axe temporel) -----------------------
#
# Ces variantes ajoutent une dimension ``z`` : la faire évoluer produit une
# animation **cohérente** des champs de bruit (le motif se déforme continûment
# au lieu de scintiller comme le ferait un simple re-seed par frame). Elles ne
# coïncident pas au pixel près avec leur version 2D à ``z = 0`` (tables de
# gradients différentes) : leur usage est piloté par le drapeau ``noise_3d`` de
# la couche, si bien que les œuvres statiques (2D) restent inchangées.

_GRAD3 = np.array(
    [[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
     [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
     [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]],
    dtype=np.float64,
)


def perlin3d(x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int) -> np.ndarray:
    """Bruit de Perlin 3D vectorisé. Résultat dans ~``[-1, 1]``."""
    perm = _permutation(seed)

    xi0 = np.floor(x).astype(np.int64)
    yi0 = np.floor(y).astype(np.int64)
    zi0 = np.floor(z).astype(np.int64)
    xf = x - xi0
    yf = y - yi0
    zf = z - zi0
    u, v, w = _fade(xf), _fade(yf), _fade(zf)
    xi, yi, zi = xi0 & 255, yi0 & 255, zi0 & 255

    def grad(ix, iy, iz, dx, dy, dz):
        idx = perm[(perm[(perm[ix & 255] + (iy & 255)) & 255] + (iz & 255)) & 255] % 12
        return _GRAD3[idx, 0] * dx + _GRAD3[idx, 1] * dy + _GRAD3[idx, 2] * dz

    n000 = grad(xi, yi, zi, xf, yf, zf)
    n100 = grad(xi + 1, yi, zi, xf - 1, yf, zf)
    n010 = grad(xi, yi + 1, zi, xf, yf - 1, zf)
    n110 = grad(xi + 1, yi + 1, zi, xf - 1, yf - 1, zf)
    n001 = grad(xi, yi, zi + 1, xf, yf, zf - 1)
    n101 = grad(xi + 1, yi, zi + 1, xf - 1, yf, zf - 1)
    n011 = grad(xi, yi + 1, zi + 1, xf, yf - 1, zf - 1)
    n111 = grad(xi + 1, yi + 1, zi + 1, xf - 1, yf - 1, zf - 1)

    x00 = _lerp(n000, n100, u)
    x10 = _lerp(n010, n110, u)
    x01 = _lerp(n001, n101, u)
    x11 = _lerp(n011, n111, u)
    y0 = _lerp(x00, x10, v)
    y1 = _lerp(x01, x11, v)
    return _lerp(y0, y1, w)


def fbm3d(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int, octaves: int = 5,
    lacunarity: float = 2.0, gain: float = 0.5,
) -> np.ndarray:
    """Somme fractale d'octaves de Perlin 3D. Résultat renormalisé dans ~``[-1, 1]``."""
    total = np.zeros_like(x)
    freq, amp, norm = 1.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * perlin3d(x * freq, y * freq, z * freq, seed + o * 101)
        norm += amp
        freq *= lacunarity
        amp *= gain
    return total / max(norm, 1e-9)


def _hash01_3d(ix, iy, iz, seed: int, salt: int) -> np.ndarray:
    """Hachage entier déterministe d'une cellule 3D vers ``[0, 1)``."""
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647
         + seed * 2246822519 + salt * 3266489917)
    h = (h ^ (h >> np.int64(13))) * 1274126177
    h = h ^ (h >> np.int64(16))
    return (h & 0xFFFFFF).astype(np.float64) / float(0x1000000)


def worley3d(x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int) -> np.ndarray:
    """Bruit cellulaire de Worley 3D (distance F1). Résultat dans ~``[0, 1]``."""
    cx = np.floor(x).astype(np.int64)
    cy = np.floor(y).astype(np.int64)
    cz = np.floor(z).astype(np.int64)
    best = np.full(x.shape, np.inf)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny, nz = cx + dx, cy + dy, cz + dz
                fx = nx + _hash01_3d(nx, ny, nz, seed, 1)
                fy = ny + _hash01_3d(nx, ny, nz, seed, 2)
                fz = nz + _hash01_3d(nx, ny, nz, seed, 3)
                dist = (x - fx) ** 2 + (y - fy) ** 2 + (z - fz) ** 2
                best = np.minimum(best, dist)
    return np.clip(np.sqrt(best), 0.0, 1.0)


_F3 = 1.0 / 3.0
_G3 = 1.0 / 6.0


def simplex3d(x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int) -> np.ndarray:
    """Bruit Simplex 3D (Gustavson), vectorisé. Résultat dans ~``[-1, 1]``."""
    perm = _permutation(seed)
    pmod12 = perm % 12

    s = (x + y + z) * _F3
    i = np.floor(x + s).astype(np.int64)
    j = np.floor(y + s).astype(np.int64)
    k = np.floor(z + s).astype(np.int64)
    t = (i + j + k) * _G3
    x0 = x - (i - t)
    y0 = y - (j - t)
    z0 = z - (k - t)

    # Détermine l'ordre des sommets du simplexe (rangs des coordonnées).
    ge_xy = x0 >= y0
    ge_yz = y0 >= z0
    ge_xz = x0 >= z0
    i1, j1, k1, i2, j2, k2 = _simplex3d_offsets(ge_xy, ge_yz, ge_xz)

    x1 = x0 - i1 + _G3
    y1 = y0 - j1 + _G3
    z1 = z0 - k1 + _G3
    x2 = x0 - i2 + 2.0 * _G3
    y2 = y0 - j2 + 2.0 * _G3
    z2 = z0 - k2 + 2.0 * _G3
    x3 = x0 - 1.0 + 3.0 * _G3
    y3 = y0 - 1.0 + 3.0 * _G3
    z3 = z0 - 1.0 + 3.0 * _G3

    ii, jj, kk = i & 255, j & 255, k & 255
    gi0 = pmod12[ii + perm[jj + perm[kk]]]
    gi1 = pmod12[ii + i1 + perm[jj + j1 + perm[kk + k1]]]
    gi2 = pmod12[ii + i2 + perm[jj + j2 + perm[kk + k2]]]
    gi3 = pmod12[ii + 1 + perm[jj + 1 + perm[kk + 1]]]

    def _corner(gi, xx, yy, zz):
        tt = 0.6 - xx * xx - yy * yy - zz * zz
        g = _GRAD3[gi]
        contrib = (tt ** 4) * (g[..., 0] * xx + g[..., 1] * yy + g[..., 2] * zz)
        return np.where(tt < 0, 0.0, contrib)

    total = (_corner(gi0, x0, y0, z0) + _corner(gi1, x1, y1, z1)
             + _corner(gi2, x2, y2, z2) + _corner(gi3, x3, y3, z3))
    return 32.0 * total


def _simplex3d_offsets(ge_xy, ge_yz, ge_xz):
    """Seconds/premiers offsets du simplexe 3D à partir des trois comparaisons."""
    # Premier sommet (rang 1).
    i1 = (ge_xy & ge_xz)
    j1 = (~ge_xy & ge_yz)
    k1 = (~ge_xz & ~ge_yz)
    # Deuxième sommet (rang 2) = au moins deux des trois comparaisons favorables.
    i2 = ge_xy | ge_xz
    j2 = (~ge_xy) | ge_yz
    k2 = ~(ge_xz & ge_yz)
    to_i = lambda b: b.astype(np.int64)
    return to_i(i1), to_i(j1), to_i(k1), to_i(i2), to_i(j2), to_i(k2)


def sample3d(
    kind: str, x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int
) -> np.ndarray:
    """Dispatch 3D. ``z`` = axe temporel. Sortie normalisée dans ~``[-1, 1]``."""
    if kind == "perlin":
        return perlin3d(x, y, z, seed)
    if kind == "simplex":
        return simplex3d(x, y, z, seed)
    if kind == "fbm":
        return fbm3d(x, y, z, seed)
    if kind == "worley":
        return worley3d(x, y, z, seed) * 2.0 - 1.0
    raise ValueError(f"Type de bruit inconnu : {kind!r}")
