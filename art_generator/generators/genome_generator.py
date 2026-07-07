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


def _ink_palette(rng: RNG) -> PaletteGenome:
    """Palette de pigment pour l'encre : teintes **sombres** et saturées.

    Le modèle soustractif assombrit le support en proportion de ``1 - couleur`` :
    un pigment sombre (luminosité HSL basse) donne donc des formes lisibles sur
    papier clair.
    """
    return PaletteGenome(
        mode="hsl",
        hue=(rng.uniform(0.0, 1.0), rng.uniform(0.05, 0.3)),
        sat=rng.uniform(0.5, 0.95),
        val=rng.uniform(0.16, 0.34),  # luminosité L basse = pigment sombre
    )


def _light_background(rng: RNG) -> tuple[str, dict]:
    """Fond pour le light painting additif : sombre, éventuellement dégradé/radial."""
    kind = rng.choice(["black", "gradient", "radial"], weights=[0.4, 0.3, 0.3])
    vignette = rng.uniform(0.15, 0.45) if rng.chance(0.5) else 0.0
    if kind == "black":
        return "black", {"vignette": vignette}
    tint = (rng.uniform(0.0, 0.12), rng.uniform(0.0, 0.12), rng.uniform(0.02, 0.16))
    if kind == "gradient":
        return "gradient", {
            "top": tint, "bottom": (0.0, 0.0, 0.0),
            "angle": rng.uniform(0.0, 180.0) if rng.chance(0.6) else None,
            "vignette": vignette,
        }
    return "radial", {
        "inner": tint, "outer": (0.0, 0.0, 0.0),
        "radius": rng.uniform(0.6, 0.95),
        "vignette": vignette,
    }


def _paper_background(rng: RNG) -> tuple[str, dict]:
    """Fond « papier » clair pour l'encre soustractive."""
    kind = rng.choice(["white", "radial", "gradient"], weights=[0.4, 0.35, 0.25])
    vignette = rng.uniform(0.1, 0.3) if rng.chance(0.6) else 0.0
    light = rng.uniform(0.92, 0.99)
    warm = (light, light * rng.uniform(0.97, 1.0), light * rng.uniform(0.93, 0.99))
    if kind == "white":
        return "white", {"vignette": vignette}
    if kind == "radial":
        edge = tuple(c * rng.uniform(0.82, 0.94) for c in warm)
        return "radial", {
            "inner": warm, "outer": edge,
            "radius": rng.uniform(0.7, 1.0), "vignette": vignette,
        }
    bottom = tuple(c * rng.uniform(0.85, 0.95) for c in warm)
    return "gradient", {
        "top": warm, "bottom": bottom,
        "angle": rng.uniform(0.0, 180.0) if rng.chance(0.5) else None,
        "vignette": vignette,
    }


def generate(
    seed: int, width: int = 1600, height: int = 1600
) -> ArtworkGenome:
    """Construit un génome reproductible pour ``seed``."""
    rng = RNG(seed)

    # Médium (Phase 4) : light painting additif (majoritaire) ou encre soustractive.
    ink = rng.chance(0.25)
    render_model = "ink" if ink else "light"

    family = rng.choice(
        registry.families(), weights=None  # équiprobable entre familles disponibles
    )
    base_palette = _ink_palette(rng) if ink else procedural.random_palette(rng)
    n_layers = rng.choice([1, 2, 3], weights=[0.45, 0.35, 0.20])

    symmetry = rng.choice(_SYMMETRIES, weights=[0.4, 0.2, 0.25, 0.15])
    symmetry_order = rng.randint(3, 8)

    # Cadrage (Phase 4d) : la moitié des œuvres cadre sur le cœur dense de la forme.
    framing = rng.choice(["box", "density"], weights=[0.55, 0.45])

    layers: list[LayerGenome] = []
    for i in range(n_layers):
        layer_family = family if i == 0 else rng.choice(registry.families())
        if i == 0:
            palette = base_palette
        elif ink:
            palette = _ink_palette(rng)
        else:
            palette = _related_palette(base_palette, rng)
        layers.append(
            LayerGenome(
                equation_family=layer_family,
                equation_params=quality.viable_params(layer_family, rng),
                n_points=int(_base_points(layer_family) * rng.uniform(0.7, 1.1)),
                palette=palette,
                color_by="velocity" if layer_family == "attractor" else "t",
                blend_mode="add" if i == 0 else rng.choice(["add", "screen"]),
                opacity=1.0 if i == 0 else rng.uniform(0.4, 0.8),
                render_model=render_model,
                framing=framing,
                thickness=rng.choice([1.0, 1.0, 2.0]),
                glow=(rng.uniform(0.1, 0.35) if ink else rng.uniform(0.4, 0.85)),
                exposure=(rng.uniform(1.1, 1.8) if ink else rng.uniform(0.8, 1.6)),
                symmetry=symmetry if i == 0 else rng.choice(["none", symmetry]),
                symmetry_order=symmetry_order,
                **_noise_settings(rng),
            )
        )

    background, background_params = (
        _paper_background(rng) if ink else _light_background(rng)
    )

    return ArtworkGenome(
        seed=seed,
        width=width,
        height=height,
        background=background,
        background_params=background_params,
        layers=layers,
        title=f"Genome #{seed}",
    )
