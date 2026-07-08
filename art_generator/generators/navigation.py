"""Navigation dans l'espace des génomes (Phase 6).

Une œuvre = un génome (voir :mod:`art_generator.core.genome`). Explorer l'espace
des œuvres revient donc à se déplacer dans l'espace des génomes. Ce module fournit
deux mouvements, tous deux **déterministes** (pilotés par un :class:`RNG`) et
produisant des génomes **sérialisables** :

* :func:`mutate` — un *petit pas* vers un génome voisin : perturbation douce des
  champs visuellement significatifs (palette, lumière, opacité, symétrie, bruit,
  fond). Les ``equation_params`` ne sont **pas** touchés, ce qui préserve la
  viabilité de la forme (pas de risque d'image noire, cf. :mod:`generators.quality`).
* :func:`reroll_equations` — un *saut* plus franc : re-tirage de paramètres
  d'équation **viables** pour chaque couche (la forme change, la mise en scène
  reste).

Aucun de ces mouvements ne modifie le génome d'origine (copie profonde).
"""

from __future__ import annotations

import copy

from ..core.genome import ArtworkGenome, LayerGenome, PaletteGenome
from ..core.rng import RNG

_SYMMETRIES = ["none", "mirror", "radial", "kaleidoscope"]


def _clamp(value: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, value)))


def _jitter(rng: RNG, value: float, lo: float, hi: float, amount: float) -> float:
    """Perturbe ``value`` par un bruit gaussien proportionnel à l'étendue admise."""
    span = hi - lo
    return _clamp(value + rng.normal(0.0, amount * span), lo, hi)


def _mutate_palette(palette: PaletteGenome, rng: RNG, amount: float) -> None:
    """Décale une palette dans son voisinage chromatique, selon son mode."""
    if palette.mode == "cosine":
        palette.phase = tuple(
            (p + rng.normal(0.0, 0.15 * amount)) % 1.0 for p in palette.phase
        )
        if rng.chance(0.3):
            palette.freq = tuple(
                _clamp(f + rng.normal(0.0, 0.25 * amount), 0.3, 3.0) for f in palette.freq
            )
    elif palette.mode in ("hsv", "hsl"):
        hue0 = (palette.hue[0] + rng.normal(0.0, 0.1 * amount)) % 1.0
        palette.hue = (hue0, _clamp(palette.hue[1] + rng.normal(0.0, 0.1 * amount), 0.0, 1.0))
        palette.sat = _clamp(palette.sat + rng.normal(0.0, 0.1 * amount), 0.0, 1.0)
        palette.val = _clamp(palette.val + rng.normal(0.0, 0.08 * amount), 0.05, 1.0)
    # mode 'gradient' : les arrêts encodent déjà la couleur, on les laisse tels quels.


def _mutate_layer(layer: LayerGenome, rng: RNG, amount: float) -> None:
    """Perturbe les réglages de mise en scène d'une couche (jamais sa forme)."""
    layer.opacity = _jitter(rng, layer.opacity, 0.2, 1.0, amount)
    layer.glow = _jitter(rng, layer.glow, 0.05, 1.0, amount)
    layer.exposure = _jitter(rng, layer.exposure, 0.6, 2.0, amount)
    if rng.chance(0.3):
        layer.thickness = float(rng.choice([1.0, 2.0, 3.0]))
    if layer.symmetry != "none" and rng.chance(0.3):
        layer.symmetry_order = int(_clamp(layer.symmetry_order + rng.choice([-1, 1]), 2, 12))
    if rng.chance(0.15):
        layer.symmetry = rng.choice(_SYMMETRIES)
    if layer.noise_type != "none":
        layer.warp = _jitter(rng, layer.warp, 0.0, 0.5, amount)
        layer.color_noise = _jitter(rng, layer.color_noise, 0.0, 0.5, amount)
        layer.light_noise = _jitter(rng, layer.light_noise, 0.0, 0.9, amount)
    _mutate_palette(layer.palette, rng, amount)


def mutate(genome: ArtworkGenome, seed: int, amount: float = 0.3) -> ArtworkGenome:
    """Renvoie un génome **voisin** de ``genome`` (petit pas déterministe).

    ``amount`` (0 → 1) règle l'amplitude du pas. Seuls les champs visuels sont
    perturbés : la forme (``equation_params``) est préservée, donc l'œuvre reste
    viable. Déterministe en ``(genome, seed, amount)``.
    """
    rng = RNG(seed)
    variant = copy.deepcopy(genome)

    params = dict(variant.background_params)
    if "vignette" in params:
        params["vignette"] = _jitter(rng, params.get("vignette", 0.0), 0.0, 0.6, amount)
    elif rng.chance(0.3):
        params["vignette"] = _jitter(rng, 0.0, 0.0, 0.5, amount)
    if variant.background == "gradient" and rng.chance(0.4):
        base_angle = params.get("angle") or 0.0
        params["angle"] = _jitter(rng, base_angle, 0.0, 180.0, amount)
    variant.background_params = params

    for layer in variant.layers:
        _mutate_layer(layer, rng, amount)

    variant.comment = f"variation (seed navigation={seed}, pas={amount})"
    return variant


def reroll_equations(genome: ArtworkGenome, seed: int) -> ArtworkGenome:
    """Renvoie un génome où **la forme** de chaque couche est re-tirée (viable).

    La mise en scène (palettes, fond, opacités, symétries…) est conservée ; seuls
    les ``equation_params`` changent, garantis viables par :mod:`generators.quality`.
    Déterministe en ``(genome, seed)``.
    """
    from . import quality  # import local : évite une dépendance à l'import du module

    rng = RNG(seed)
    variant = copy.deepcopy(genome)
    for layer in variant.layers:
        layer.equation_params = quality.viable_params(layer.equation_family, rng)
    variant.comment = f"re-tirage des formes (seed navigation={seed})"
    return variant
