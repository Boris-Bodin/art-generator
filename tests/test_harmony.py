"""Tests des contraintes d'harmonie et des palettes nommées."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.core.rng import RNG
from art_generator.exporters import genome_io
from art_generator.palettes import procedural as P


@pytest.mark.parametrize("scheme", list(P.HARMONY_SCHEMES))
def test_harmonic_palette_valid(scheme):
    palette = P.harmonic_palette(RNG(3), scheme)
    assert palette.mode == "gradient"
    assert palette.name == f"harmony:{scheme}"
    assert len(palette.stops) == len(P.HARMONY_SCHEMES[scheme]) or scheme == "monochrome"
    colors = P.apply(np.linspace(0, 1, 50), palette)
    assert colors.shape == (50, 3)
    assert colors.min() >= 0.0 and colors.max() <= 1.0


def test_harmonic_is_deterministic():
    a = P.harmonic_palette(RNG(9), "triadic")
    b = P.harmonic_palette(RNG(9), "triadic")
    assert a.stops == b.stops


@pytest.mark.parametrize("name", P.named_names())
def test_named_palette_valid(name):
    palette = P.named_palette(name)
    assert palette.name == name
    colors = P.apply(np.linspace(0, 1, 50), palette)
    assert colors.min() >= 0.0 and colors.max() <= 1.0


def test_named_palette_unknown_raises():
    with pytest.raises(KeyError):
        P.named_palette("inexistante")


def test_hsl_to_rgb_scalar_and_array():
    assert P.hsl_to_rgb(0.3, 0.8, 0.5).shape == (3,)
    assert P.hsl_to_rgb(np.linspace(0, 1, 12), 0.8, 0.5).shape == (12, 3)


def test_round_trip_harmonic_and_named(tmp_path):
    genome = ag.generate(41, 200, 200)
    genome.layers[0].palette = P.harmonic_palette(RNG(1), "split_complementary")
    if len(genome.layers) > 1:
        genome.layers[1].palette = P.named_palette("ocean")
    path = genome_io.save(genome, tmp_path / "g.json")
    reloaded = genome_io.load(path)
    a = np.asarray(Engine().render(genome))
    b = np.asarray(Engine().render(reloaded))
    assert np.array_equal(a, b)
    assert reloaded.layers[0].palette.name == "harmony:split_complementary"
