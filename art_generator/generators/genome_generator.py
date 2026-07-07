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


def _related_palette(base: PaletteGenome, rng: RNG) -> PaletteGenome:
    """Palette apparentée à ``base`` (phases décalées) pour cohérence de couches."""
    shift = rng.uniform(0.05, 0.2)
    return PaletteGenome(
        mode=base.mode,
        offset=base.offset,
        amp=base.amp,
        freq=base.freq,
        phase=tuple(p + shift for p in base.phase),
    )


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

    # densité de points selon la famille (les attracteurs aiment la densité)
    base_points = 260_000 if family == "attractor" else 180_000

    layers: list[LayerGenome] = []
    for i in range(n_layers):
        layer_family = family if i == 0 else rng.choice(registry.families())
        palette = base_palette if i == 0 else _related_palette(base_palette, rng)
        layers.append(
            LayerGenome(
                equation_family=layer_family,
                equation_params=quality.viable_params(layer_family, rng),
                n_points=int(base_points * rng.uniform(0.7, 1.1)),
                palette=palette,
                color_by="velocity" if layer_family == "attractor" else "t",
                blend_mode="add" if i == 0 else rng.choice(["add", "screen"]),
                opacity=1.0 if i == 0 else rng.uniform(0.4, 0.8),
                thickness=rng.choice([1.0, 1.0, 2.0]),
                glow=rng.uniform(0.4, 0.85),
                exposure=rng.uniform(0.8, 1.6),
                symmetry=symmetry if i == 0 else rng.choice(["none", symmetry]),
                symmetry_order=symmetry_order,
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
