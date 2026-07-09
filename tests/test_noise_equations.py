"""Tests du bruit, des familles d'équations, des palettes et du warp."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.core.genome import PaletteGenome
from art_generator.exporters import genome_io
from art_generator.noise import fields
from art_generator.palettes import procedural


@pytest.mark.parametrize("kind", ["perlin", "fbm", "worley"])
def test_noise_is_deterministic_and_bounded(kind):
    x = np.linspace(0, 8, 500)
    y = np.linspace(3, 11, 500)
    a = fields.sample(kind, x, y, seed=42)
    b = fields.sample(kind, x, y, seed=42)
    assert np.array_equal(a, b)
    assert np.abs(a).max() <= 1.01
    # une seed différente donne un champ différent
    c = fields.sample(kind, x, y, seed=43)
    assert not np.array_equal(a, c)


@pytest.mark.parametrize("mode", ["cosine", "hsv", "gradient"])
def test_palette_modes_produce_valid_rgb(mode):
    from art_generator.core.rng import RNG

    factory = {
        "cosine": procedural._random_cosine,
        "hsv": procedural._random_hsv,
        "gradient": procedural._random_gradient,
    }[mode]
    palette = factory(RNG(7))
    colors = procedural.apply(np.linspace(0, 1, 64), palette)
    assert colors.shape == (64, 3)
    assert colors.min() >= 0.0 and colors.max() <= 1.0


def test_new_families_registered():
    from art_generator.equations import registry

    for fam in ("vector_field", "complex", "fractal"):
        assert fam in registry.families()


def test_round_trip_with_noise_and_new_palettes(tmp_path):
    # Force une couche avec warp par bruit et palette HSV, puis vérifie
    # que la sérialisation préserve tout au pixel près.
    genome = ag.generate(24, 256, 256)  # seed connue mêlant fractal + bruit
    genome.layers[0].palette = PaletteGenome(mode="hsv", hue=(0.1, 0.7), sat=0.8, val=0.95)
    genome.layers[0].noise_type = "fbm"
    genome.layers[0].warp = 0.2
    genome.layers[0].color_noise = 0.15
    path = genome_io.save(genome, tmp_path / "g.json")
    reloaded = genome_io.load(path)
    a = np.asarray(Engine().render(genome))
    b = np.asarray(Engine().render(reloaded))
    assert np.array_equal(a, b)


def test_domain_warp_changes_image():
    base = ag.generate(25, 256, 256)
    warped = ag.generate(25, 256, 256)
    for layer in warped.layers:
        layer.noise_type = "perlin"
        layer.warp = 0.4
        layer.noise_seed = 1
    a = np.asarray(Engine().render(base))
    b = np.asarray(Engine().render(warped))
    assert not np.array_equal(a, b)
