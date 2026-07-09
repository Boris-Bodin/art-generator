"""Tests du bruit Simplex, des palettes HSL et de la modulation lumière/épaisseur."""

from __future__ import annotations

import numpy as np

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.core.genome import LayerGenome, PaletteGenome
from art_generator.core.rng import RNG
from art_generator.equations import registry
from art_generator.exporters import genome_io
from art_generator.noise import fields
from art_generator.palettes import procedural
from art_generator.renderers import accumulation


def test_simplex_deterministic_bounded_continuous():
    x = np.linspace(0, 12, 1000)
    y = np.cos(x) * 2.0
    a = fields.simplex2d(x, y, 11)
    assert np.array_equal(a, fields.simplex2d(x, y, 11))
    assert not np.array_equal(a, fields.simplex2d(x, y, 12))
    assert np.abs(a).max() <= 1.0
    # continuité : pas de discontinuités sur un échantillonnage fin
    fine = fields.simplex2d(np.linspace(0, 1, 2000), np.zeros(2000), 3)
    assert np.abs(np.diff(fine)).max() < 0.05


def test_simplex_available_via_dispatch():
    x = np.linspace(0, 5, 100)
    assert fields.sample("simplex", x, x, 1).shape == x.shape


def test_hsl_palette_valid_rgb():
    palette = procedural._random_hsl(RNG(9))
    colors = procedural.apply(np.linspace(0, 1, 48), palette)
    assert colors.shape == (48, 3)
    assert colors.min() >= 0.0 and colors.max() <= 1.0


def _layer(**kw):
    params = dict(equation_family="parametric", n_points=80_000, thickness=1.0)
    params.update(kw)
    return LayerGenome(**params)


def _render(layer):
    # render_layer renvoie (color, alpha) ; l'emprise se lit
    # sur la couverture alpha (dense = allumé, vide = transparent).
    eq = registry.build("parametric", registry.random_params("parametric", RNG(4)))
    _, alpha = accumulation.render_layer(eq, layer, 400, 400)
    return alpha


def test_thickness_noise_increases_coverage():
    base = _render(_layer())
    thick = _render(_layer(noise_type="simplex", thickness_noise=3.0, noise_seed=1))
    assert (thick > 0).sum() > (base > 0).sum()


def test_light_noise_changes_render_without_new_pixels():
    # glow=0 pour isoler l'emprise de l'accumulation (le flou du halo la diffuse).
    base = _render(_layer(glow=0.0))
    lit = _render(_layer(glow=0.0, noise_type="perlin", light_noise=0.6, noise_seed=2))
    assert not np.array_equal(base, lit)
    # la lumière module l'intensité, pas l'emprise : mêmes pixels allumés
    assert (base > 0).sum() == (lit > 0).sum()


def test_round_trip_hsl_and_modulation(tmp_path):
    genome = ag.generate(41, 256, 256)
    genome.layers[0].palette = PaletteGenome(mode="hsl", hue=(0.2, 0.6), sat=0.8, val=0.5)
    genome.layers[0].noise_type = "simplex"
    genome.layers[0].light_noise = 0.5
    genome.layers[0].thickness_noise = 2.0
    path = genome_io.save(genome, tmp_path / "g.json")
    reloaded = genome_io.load(path)
    a = np.asarray(Engine().render(genome))
    b = np.asarray(Engine().render(reloaded))
    assert np.array_equal(a, b)
