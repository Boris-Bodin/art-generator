"""Palettes procédurales.

Les couleurs ne sont jamais choisies dans une liste : elles sont *calculées*.
La palette par défaut est un gradient cosinus (Inigo Quilez) :

    couleur(t) = offset + amp * cos(2*pi * (freq * t + phase))

appliqué canal par canal. Ce modèle produit des dégradés cycliques doux et une
grande diversité tout en gardant une cohérence de famille.
"""

from __future__ import annotations

import numpy as np

from ..core.genome import PaletteGenome

_TWO_PI = 2.0 * np.pi


def cosine_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Mappe un tableau de valeurs ``t in [0, 1]`` vers des couleurs RGB.

    Returns:
        Tableau ``(N, 3)`` de flottants dans ``[0, 1]``.
    """
    t = np.asarray(t, dtype=np.float64).reshape(-1, 1)
    offset = np.asarray(palette.offset, dtype=np.float64)
    amp = np.asarray(palette.amp, dtype=np.float64)
    freq = np.asarray(palette.freq, dtype=np.float64)
    phase = np.asarray(palette.phase, dtype=np.float64)

    rgb = offset + amp * np.cos(_TWO_PI * (freq * t + phase))
    return np.clip(rgb, 0.0, 1.0)


def hsv_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Palette HSV : la teinte parcourt ``hue`` le long de ``t``.

    Saturation et valeur sont constantes. Conversion HSV→RGB vectorisée.
    """
    t = np.asarray(t, dtype=np.float64)
    h = (palette.hue[0] + t * palette.hue[1]) % 1.0
    s = np.full_like(h, palette.sat)
    v = np.full_like(h, palette.val)

    i = np.floor(h * 6.0).astype(np.int64)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    tt = v * (1.0 - (1.0 - f) * s)
    i = i % 6

    r = np.choose(i, [v, q, p, p, tt, v])
    g = np.choose(i, [tt, v, v, q, p, p])
    b = np.choose(i, [p, p, tt, v, v, q])
    return np.clip(np.column_stack((r, g, b)), 0.0, 1.0)


def hsl_to_rgb(h, s, l) -> np.ndarray:
    """Conversion HSL→RGB vectorisée. ``h``/``s``/``l`` scalaires ou tableaux.

    Returns un tableau ``(N, 3)`` dans ``[0, 1]``.
    """
    h = np.asarray(h, dtype=np.float64)
    s = np.broadcast_to(np.asarray(s, dtype=np.float64), h.shape)
    l = np.broadcast_to(np.asarray(l, dtype=np.float64), h.shape)

    c = (1.0 - np.abs(2.0 * l - 1.0)) * s
    hp = (h % 1.0) * 6.0
    x = c * (1.0 - np.abs(hp % 2.0 - 1.0))
    m = l - c / 2.0

    z = np.zeros_like(h)
    seg = np.floor(hp).astype(np.int64) % 6
    r = np.choose(seg, [c, x, z, z, x, c]) + m
    g = np.choose(seg, [x, c, c, x, z, z]) + m
    b = np.choose(seg, [z, z, x, c, c, x]) + m
    return np.clip(np.stack((r, g, b), axis=-1), 0.0, 1.0)


def hsl_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Palette HSL : teinte parcourant ``hue``, ``sat`` fixe, luminosité = ``val``.

    Contrairement au HSV, le HSL rend la luminosité (``L``) symétrique : ``L=0.5``
    donne la couleur la plus saturée, ``L→1`` tend vers le blanc. On réutilise le
    champ ``val`` du génome comme luminosité ``L``.
    """
    t = np.asarray(t, dtype=np.float64)
    h = palette.hue[0] + t * palette.hue[1]
    return hsl_to_rgb(h, palette.sat, palette.val)


def gradient_palette(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Dégradé multi-arrêts : interpolation linéaire entre arrêts ``(pos, r, g, b)``."""
    t = np.asarray(t, dtype=np.float64)
    stops = sorted(palette.stops, key=lambda s: s[0])
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1:] for s in stops])  # (S, 3)
    r = np.interp(t, pos, cols[:, 0])
    g = np.interp(t, pos, cols[:, 1])
    b = np.interp(t, pos, cols[:, 2])
    return np.clip(np.column_stack((r, g, b)), 0.0, 1.0)


def apply(t: np.ndarray, palette: PaletteGenome) -> np.ndarray:
    """Point d'entrée du moteur : dispatch selon ``palette.mode``."""
    if palette.mode == "cosine":
        return cosine_palette(t, palette)
    if palette.mode == "hsv":
        return hsv_palette(t, palette)
    if palette.mode == "hsl":
        return hsl_palette(t, palette)
    if palette.mode == "gradient":
        return gradient_palette(t, palette)
    raise ValueError(f"Mode de palette inconnu : {palette.mode!r}")


def _random_cosine(rng) -> PaletteGenome:
    base_phase = rng.uniform(0.0, 1.0)
    return PaletteGenome(
        mode="cosine",
        offset=(rng.uniform(0.4, 0.6), rng.uniform(0.4, 0.6), rng.uniform(0.4, 0.6)),
        amp=(rng.uniform(0.35, 0.55), rng.uniform(0.35, 0.55), rng.uniform(0.35, 0.55)),
        freq=(rng.uniform(0.7, 1.6), rng.uniform(0.7, 1.6), rng.uniform(0.7, 1.6)),
        phase=(
            base_phase,
            base_phase + rng.uniform(0.1, 0.4),
            base_phase + rng.uniform(0.4, 0.8),
        ),
    )


def _random_hsv(rng) -> PaletteGenome:
    return PaletteGenome(
        mode="hsv",
        hue=(rng.uniform(0.0, 1.0), rng.uniform(0.2, 0.9)),
        sat=rng.uniform(0.55, 0.95),
        val=rng.uniform(0.85, 1.0),
    )


def _random_hsl(rng) -> PaletteGenome:
    return PaletteGenome(
        mode="hsl",
        hue=(rng.uniform(0.0, 1.0), rng.uniform(0.2, 0.9)),
        sat=rng.uniform(0.55, 0.95),
        val=rng.uniform(0.45, 0.62),  # luminosité L : proche de 0.5 = couleurs vives
    )


def _random_gradient(rng) -> PaletteGenome:
    """Dégradé dont les arrêts sont échantillonnés sur une palette cosinus.

    Ancrer les couleurs sur un cosinus conserve la parenté chromatique de famille.
    """
    base = _random_cosine(rng)
    n_stops = rng.randint(3, 5)
    positions = sorted(rng.uniform(0.0, 1.0) for _ in range(n_stops))
    positions[0], positions[-1] = 0.0, 1.0
    sampled = cosine_palette(np.array(positions), base)
    stops = [[positions[i], *sampled[i].tolist()] for i in range(len(positions))]
    return PaletteGenome(mode="gradient", stops=stops)


# --- Contraintes d'harmonie -------------------------------------------------
# Décalages de teinte (en tours, 1.0 = 360°) définissant chaque schéma de la
# roue chromatique. L'harmonie est ainsi *garantie par construction* plutôt que
# laissée au hasard des tirages.
HARMONY_SCHEMES: dict[str, list[float]] = {
    "monochrome": [0.0],
    "analogous": [-1 / 12, 0.0, 1 / 12],       # teintes voisines (±30°)
    "complementary": [0.0, 0.5],               # opposées (180°)
    "split_complementary": [0.0, 5 / 12, 7 / 12],  # 150° / 210°
    "triadic": [0.0, 1 / 3, 2 / 3],            # 120° / 240°
    "tetradic": [0.0, 0.25, 0.5, 0.75],        # carré
}


def harmonic_palette(rng, scheme: str | None = None) -> PaletteGenome:
    """Dégradé bâti sur un schéma d'harmonie de la roue chromatique.

    On tire une teinte de base puis on *dérive* les autres teintes par la règle
    du schéma (analogue, complémentaire, triadique…), avant de les convertir en
    arrêts de dégradé. Le résultat réutilise le mode ``gradient`` du moteur.
    """
    scheme = scheme or rng.choice(list(HARMONY_SCHEMES))
    h0 = rng.uniform(0.0, 1.0)
    sat = rng.uniform(0.6, 0.95)
    offsets = HARMONY_SCHEMES[scheme]

    if scheme == "monochrome":
        # une seule teinte, luminosité parcourue du sombre au clair (profondeur)
        lights = [0.25, 0.45, 0.68, 0.85]
        colors = [hsl_to_rgb(h0, sat, l) for l in lights]
    else:
        # légère variation de luminosité par arrêt pour éviter la platitude
        colors = [hsl_to_rgb((h0 + d) % 1.0, sat, rng.uniform(0.45, 0.62)) for d in offsets]

    positions = np.linspace(0.0, 1.0, len(colors))
    stops = [[float(positions[i]), *map(float, colors[i])] for i in range(len(colors))]
    return PaletteGenome(mode="gradient", stops=stops, name=f"harmony:{scheme}")


# --- Palettes nommées (curation) --------------------------------------------
# Petit catalogue d'ambiances reconnaissables, définies comme dégradés RGB.
NAMED_PALETTES: dict[str, list[tuple[float, float, float, float]]] = {
    "nebula": [(0.0, 0.03, 0.02, 0.15), (0.4, 0.28, 0.05, 0.5),
               (0.7, 0.8, 0.15, 0.6), (1.0, 0.25, 0.85, 0.95)],
    "ember": [(0.0, 0.05, 0.0, 0.0), (0.4, 0.6, 0.08, 0.02),
              (0.72, 1.0, 0.5, 0.05), (1.0, 1.0, 0.95, 0.72)],
    "aurora": [(0.0, 0.0, 0.15, 0.15), (0.35, 0.05, 0.7, 0.5),
               (0.7, 0.3, 0.9, 0.4), (1.0, 0.9, 0.3, 0.8)],
    "bio": [(0.0, 0.0, 0.1, 0.02), (0.4, 0.1, 0.5, 0.06),
            (0.72, 0.6, 0.9, 0.1), (1.0, 0.95, 0.98, 0.45)],
    "ocean": [(0.0, 0.0, 0.05, 0.2), (0.4, 0.0, 0.35, 0.55),
              (0.75, 0.1, 0.7, 0.82), (1.0, 0.85, 0.98, 1.0)],
    "sunset": [(0.0, 0.1, 0.02, 0.2), (0.35, 0.6, 0.05, 0.35),
               (0.7, 1.0, 0.4, 0.1), (1.0, 1.0, 0.85, 0.4)],
}


def named_palette(name: str) -> PaletteGenome:
    """Renvoie une palette nommée du catalogue."""
    if name not in NAMED_PALETTES:
        raise KeyError(f"Palette nommée inconnue : {name!r}")
    return PaletteGenome(
        mode="gradient", name=name,
        stops=[list(stop) for stop in NAMED_PALETTES[name]],
    )


def named_names() -> list[str]:
    return sorted(NAMED_PALETTES)


def _random_named(rng) -> PaletteGenome:
    return named_palette(rng.choice(named_names()))


def random_palette(rng) -> PaletteGenome:
    """Palette harmonieuse.

    Dominée par le cosinus (identité de famille) et l'harmonie garantie par
    schéma ; complétée par HSV/HSL, palettes nommées et dégradé libre.
    """
    mode = rng.choice(
        ["cosine", "harmonic", "named", "hsv", "hsl", "gradient"],
        weights=[0.34, 0.3, 0.12, 0.09, 0.08, 0.07],
    )
    if mode == "cosine":
        return _random_cosine(rng)
    if mode == "harmonic":
        return harmonic_palette(rng)
    if mode == "named":
        return _random_named(rng)
    if mode == "hsv":
        return _random_hsv(rng)
    if mode == "hsl":
        return _random_hsl(rng)
    return _random_gradient(rng)
