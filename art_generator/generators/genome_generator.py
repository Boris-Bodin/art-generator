"""Génération d'un génome complet à partir d'une seed.

C'est ici que naît une œuvre : la seed pilote un :class:`RNG` déterministe qui
tire une famille d'équations, ses paramètres, une ou plusieurs couches, leurs
palettes et le fond. Les contraintes de tirage (opacités décroissantes, palettes
apparentées, fond sombre, rendu additif) donnent aux œuvres une identité de
famille tout en garantissant leur unicité.
"""

from __future__ import annotations

from ..core.genome import ArtworkGenome, LayerGenome, PaletteGenome
from ..core.rng import RNG
from ..equations import registry
from ..palettes import procedural
from . import quality

_SYMMETRIES = ["none", "mirror", "radial", "kaleidoscope"]


_NOISE_TYPES = ["perlin", "simplex", "fbm", "worley"]

# densité de points indicative par famille
_POINTS = {
    "attractor": 260_000,
    "fractal": 220_000,
    "vector_field": 240_000,
    "complex": 200_000,
    "particles": 320_000,
}


def _base_points(family: str) -> int:
    return _POINTS.get(family, 180_000)


def _related_palette(base: PaletteGenome, rng: RNG) -> PaletteGenome:
    """Palette apparentée à ``base`` pour la cohérence entre couches.

    Le décalage dépend du mode : phase pour le cosinus, teinte pour le HSV ; le
    mode dégradé est repris tel quel (ses arrêts encodent déjà la couleur).
    """
    shift = rng.uniform(0.05, 0.2)
    if base.mode == "cosine":
        return PaletteGenome(
            mode="cosine", offset=base.offset, amp=base.amp, freq=base.freq,
            phase=tuple(p + shift for p in base.phase),
        )
    if base.mode in ("hsv", "hsl"):
        return PaletteGenome(
            mode=base.mode, hue=((base.hue[0] + shift) % 1.0, base.hue[1]),
            sat=base.sat, val=base.val,
        )
    return base


def _noise_settings(rng: RNG) -> dict:
    """Réglages de bruit d'une couche : warp du domaine + modulation couleur."""
    if not rng.chance(0.45):
        return {"noise_type": "none"}
    return {
        "noise_type": rng.choice(_NOISE_TYPES),
        "warp": rng.uniform(0.05, 0.3) if rng.chance(0.75) else 0.0,
        "warp_freq": rng.uniform(0.6, 3.0),
        "color_noise": rng.uniform(0.0, 0.3) if rng.chance(0.5) else 0.0,
        "light_noise": rng.uniform(0.2, 0.7) if rng.chance(0.5) else 0.0,
        "thickness_noise": rng.choice([0.0, 0.0, 2.0, 3.0]) if rng.chance(0.4) else 0.0,
        "noise_seed": rng.randint(0, 2**31 - 1),
    }


def generate(
    seed: int, width: int = 1600, height: int = 1600
) -> ArtworkGenome:
    """Construit un génome reproductible pour ``seed``."""
    rng = RNG(seed)

    family = rng.choice(
        registry.families(), weights=None  # équiprobable entre familles disponibles
    )
    base_palette = procedural.random_palette(rng)
    n_layers = rng.choice([1, 2, 3], weights=[0.45, 0.35, 0.20])

    symmetry = rng.choice(_SYMMETRIES, weights=[0.4, 0.2, 0.25, 0.15])
    symmetry_order = rng.randint(3, 8)

    layers: list[LayerGenome] = []
    for i in range(n_layers):
        layer_family = family if i == 0 else rng.choice(registry.families())
        palette = base_palette if i == 0 else _related_palette(base_palette, rng)
        layers.append(
            LayerGenome(
                equation_family=layer_family,
                equation_params=quality.viable_params(layer_family, rng),
                n_points=int(_base_points(layer_family) * rng.uniform(0.7, 1.1)),
                palette=palette,
                color_by="velocity" if layer_family == "attractor" else "t",
                blend_mode="add" if i == 0 else rng.choice(["add", "screen"]),
                opacity=1.0 if i == 0 else rng.uniform(0.4, 0.8),
                thickness=rng.choice([1.0, 1.0, 2.0]),
                glow=rng.uniform(0.4, 0.85),
                exposure=rng.uniform(0.8, 1.6),
                symmetry=symmetry if i == 0 else rng.choice(["none", symmetry]),
                symmetry_order=symmetry_order,
                **_noise_settings(rng),
            )
        )

    background = rng.choice(["black", "gradient"], weights=[0.5, 0.5])

    return ArtworkGenome(
        seed=seed,
        width=width,
        height=height,
        background=background,
        background_params={},
        layers=layers,
        title=f"Genome #{seed}",
    )
