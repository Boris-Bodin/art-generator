"""Tests du système de particules (émetteurs, forces, turbulence)."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.core.genome import ArtworkGenome, LayerGenome, PaletteGenome
from art_generator.equations import particles, registry
from art_generator.exporters import genome_io


def _params(**overrides):
    p = {
        "n_particles": 500,
        "dt": 0.03,
        "life": 30.0,
        "color_by": "age",
        "emitter": {"type": "disk", "cx": 0.0, "cy": 0.0, "radius": 0.6, "spread": 0.4},
        "forces": {"drag": 0.1, "central": 0.5, "vortex": 0.8},
        "turbulence": {"amp": 1.0, "freq": 1.2, "noise_type": "simplex", "seed": 7},
        "seed": 123,
    }
    p.update(overrides)
    return p


def test_particles_registered():
    assert "particles" in registry.families()


def test_particle_sample_is_deterministic():
    a_pts, a_val = particles.ParticleSystem(_params()).sample(40_000)
    b_pts, b_val = particles.ParticleSystem(_params()).sample(40_000)
    assert np.array_equal(a_pts, b_pts)
    assert np.array_equal(a_val, b_val)


def test_particle_values_are_normalised():
    for color_by in ("age", "speed"):
        _, values = particles.ParticleSystem(_params(color_by=color_by)).sample(40_000)
        finite = values[np.isfinite(values)]
        assert finite.min() >= 0.0
        assert finite.max() <= 1.0


def test_particle_count_scales_with_n():
    """Le nombre de points suit ``n`` : montée en charge vers le million."""
    n = 200_000
    pts, _ = particles.ParticleSystem(_params(n_particles=4000)).sample(n)
    # steps = n // n_particles ; total = steps * n_particles ~ n (à un pas près).
    assert abs(len(pts) - n) <= 4000


def test_different_forces_change_the_cloud():
    swirly, _ = particles.ParticleSystem(
        _params(forces={"drag": 0.1, "vortex": 1.4, "central": 0.0})
    ).sample(40_000)
    falling, _ = particles.ParticleSystem(
        _params(forces={"drag": 0.1, "vortex": 0.0, "central": 0.0, "gravity_y": -0.8})
    ).sample(40_000)
    assert not np.array_equal(swirly, falling)


@pytest.mark.parametrize("emitter", ["point", "disk", "ring", "line"])
def test_all_emitters_produce_points(emitter):
    pts, _ = particles.ParticleSystem(
        _params(emitter={"type": emitter, "radius": 0.6, "spread": 0.4, "length": 2.0})
    ).sample(20_000)
    assert len(pts) > 0
    assert np.isfinite(pts).all()


def test_generator_can_emit_particle_genomes():
    """Au moins une seed doit produire une œuvre à base de particules, et rendre."""
    found = False
    for seed in range(60):
        genome = ag.generate(seed, 128, 128)
        if any(layer.equation_family == "particles" for layer in genome.layers):
            img = np.asarray(Engine().render(genome))
            assert img.shape == (128, 128, 3)
            assert img.max() > 0.0  # non entièrement noire
            found = True
            break
    assert found, "aucune seed n'a produit de couche 'particles' sur 60 essais"


def test_round_trip_pixel_identical_with_particles(tmp_path):
    genome = ArtworkGenome(
        seed=1,
        width=256,
        height=256,
        background="black",
        layers=[
            LayerGenome(
                equation_family="particles",
                equation_params=_params(),
                n_points=120_000,
                palette=PaletteGenome(mode="hsv", hue=(0.5, 0.4), sat=0.8, val=1.0),
                glow=0.5,
            )
        ],
    )
    path = genome_io.save(genome, tmp_path / "particles.json")
    reloaded = genome_io.load(path)
    a = np.asarray(Engine().render(genome))
    b = np.asarray(Engine().render(reloaded))
    assert np.array_equal(a, b)
