"""Tests du moteur : déterminisme, reproductibilité, viabilité, familles."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.equations import registry
from art_generator.exporters import genome_io
from art_generator.generators import quality


def _pixels(genome):
    return np.asarray(Engine().render(genome))


def test_same_seed_is_deterministic():
    _, a = ag.render_seed(123, 256, 256)
    _, b = ag.render_seed(123, 256, 256)
    assert np.array_equal(np.asarray(a), np.asarray(b))


def test_different_seeds_differ():
    _, a = ag.render_seed(1, 256, 256)
    _, b = ag.render_seed(2, 256, 256)
    assert not np.array_equal(np.asarray(a), np.asarray(b))


def test_json_round_trip_is_pixel_identical(tmp_path):
    genome = ag.generate(777, 256, 256)
    path = genome_io.save(genome, tmp_path / "g.json")
    reloaded = genome_io.load(path)
    assert np.array_equal(_pixels(genome), _pixels(reloaded))


def test_output_is_not_blank():
    # Une œuvre doit contenir de la lumière (le contrôle de viabilité l'assure).
    for seed in (10, 50, 100, 200):
        _, img = ag.render_seed(seed, 256, 256)
        assert np.asarray(img).max() > 20, f"œuvre trop sombre pour seed={seed}"


@pytest.mark.parametrize("family", registry.families())
def test_every_family_renders(family):
    from art_generator.core.rng import RNG

    rng = RNG(3)
    params = quality.viable_params(family, rng)
    equation = registry.build(family, params)
    points, values = equation.sample(5000)
    assert points.shape[1] == 2
    assert len(points) == len(values)


def test_image_dimensions_match_genome():
    genome = ag.generate(9, 320, 240)
    img = Engine().render(genome)
    assert img.size == (320, 240)
