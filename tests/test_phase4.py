"""Tests de la Phase 4 : compositing alpha, encre soustractive, fonds, cadrage."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core import blend
from art_generator.core.background import make_background
from art_generator.core.engine import Engine
from art_generator.core.genome import ArtworkGenome, LayerGenome, PaletteGenome
from art_generator.core.rng import RNG
from art_generator.equations import registry
from art_generator.exporters import genome_io
from art_generator.generators import quality
from art_generator.renderers import accumulation
from art_generator.utils.math_utils import fit_to_canvas


# --- 4a : compositing par alpha ---------------------------------------------

def test_composite_empty_alpha_reveals_background():
    base = np.tile(np.array([0.2, 0.4, 0.6]), (4, 4, 1))
    color = np.ones((4, 4, 3))
    alpha = np.zeros((4, 4))  # aucune couverture -> le fond doit transparaître
    out = blend.composite(base, color, alpha, "normal", 1.0, "light")
    assert np.allclose(out, base)


def test_composite_light_on_black_is_premultiplied():
    """Sur fond noir, ``add`` reproduit le tampon additif ``color * alpha``."""
    base = np.zeros((5, 5, 3))
    rng = np.random.default_rng(0)
    color = rng.uniform(0, 1, (5, 5, 3))
    alpha = rng.uniform(0, 1, (5, 5))
    out = blend.composite(base, color, alpha, "add", 1.0, "light")
    assert np.allclose(out, np.clip(color * alpha[..., None], 0, 1))


def test_composite_full_alpha_normal_replaces_with_color():
    base = np.zeros((3, 3, 3))
    color = np.tile(np.array([0.3, 0.5, 0.7]), (3, 3, 1))
    alpha = np.ones((3, 3))
    out = blend.composite(base, color, alpha, "normal", 1.0, "light")
    assert np.allclose(out, color)


# --- 4b : encre soustractive -------------------------------------------------

def test_ink_darkens_light_support():
    paper = np.ones((4, 4, 3))
    pigment = np.tile(np.array([0.1, 0.1, 0.1]), (4, 4, 1))  # encre sombre
    alpha = np.ones((4, 4))
    out = blend.composite(paper, pigment, alpha, "add", 1.0, "ink")
    assert (out < paper).all()  # le pigment assombrit partout où il couvre
    assert np.allclose(out, pigment)  # a=1, base=1 -> out = pigment


def test_ink_empty_area_keeps_paper():
    paper = np.full((4, 4, 3), 0.95)
    pigment = np.zeros((4, 4, 3))
    alpha = np.zeros((4, 4))
    out = blend.composite(paper, pigment, alpha, "add", 1.0, "ink")
    assert np.allclose(out, paper)


def test_ink_layers_stack_darker():
    paper = np.ones((2, 2, 3))
    pigment = np.full((2, 2, 3), 0.2)
    alpha = np.full((2, 2), 0.8)
    once = blend.composite(paper, pigment, alpha, "add", 1.0, "ink")
    twice = blend.composite(once, pigment, alpha, "add", 1.0, "ink")
    assert (twice < once).all()


# --- 4c : fonds enrichis -----------------------------------------------------

def _bg_genome(background, params):
    return ArtworkGenome(width=32, height=24, background=background,
                         background_params=params, layers=[])


def test_radial_background_darkens_outward():
    bg = make_background(_bg_genome("radial", {
        "inner": (1.0, 1.0, 1.0), "outer": (0.0, 0.0, 0.0), "radius": 1.0}))
    center = bg[12, 16].mean()
    corner = bg[0, 0].mean()
    assert center > corner
    assert bg.shape == (24, 32, 3)


def test_directional_gradient_varies_horizontally():
    bg = make_background(_bg_genome("gradient", {
        "top": (1.0, 1.0, 1.0), "bottom": (0.0, 0.0, 0.0), "angle": 0.0}))
    # angle 0 -> variation gauche/droite (pas seulement verticale)
    assert not np.allclose(bg[:, 0], bg[:, -1])


def test_vignette_darkens_edges():
    plain = make_background(_bg_genome("white", {}))
    vig = make_background(_bg_genome("white", {"vignette": 0.6}))
    assert np.allclose(plain, 1.0)
    assert vig[0, 0].mean() < vig[12, 16].mean()  # coin plus sombre que centre


def test_unknown_background_raises():
    with pytest.raises(ValueError):
        make_background(_bg_genome("plaid", {}))


# --- 4d : cadrage par densité ------------------------------------------------

def test_density_framing_centers_on_dense_core():
    rng = np.random.default_rng(1)
    dense = rng.normal(0.0, 0.05, (5000, 2))          # amas serré à l'origine
    sparse = rng.uniform(-2.0, 2.0, (200, 2))         # bruit dispersé
    points = np.vstack((dense, sparse))

    box, _ = fit_to_canvas(points, 100, 100, center_on="box")
    dens, _ = fit_to_canvas(points, 100, 100, center_on="density")
    # Le centroïde densité place l'amas près du centre du canvas (50, 50).
    dens_center = np.median(dens, axis=0)
    assert abs(dens_center[0] - 50) < 12 and abs(dens_center[1] - 50) < 12


# --- render_layer : nouveau contrat (color, alpha) ---------------------------

def test_render_layer_returns_color_and_alpha():
    params = quality.viable_params("attractor", RNG(4))
    eq = registry.build("attractor", params)
    color, alpha = accumulation.render_layer(eq, LayerGenome(n_points=20_000), 64, 64)
    assert color.shape == (64, 64, 3)
    assert alpha.shape == (64, 64)
    assert alpha.min() >= 0.0 and alpha.max() <= 1.0


# --- invariants : déterminisme & round-trip avec les nouveautés --------------

def _ink_genome():
    return ArtworkGenome(
        seed=3, width=200, height=200,
        background="radial",
        background_params={"inner": (0.97, 0.96, 0.93),
                           "outer": (0.82, 0.80, 0.75), "vignette": 0.2},
        layers=[LayerGenome(
            equation_family="attractor",
            equation_params=quality.viable_params("attractor", RNG(3)),
            n_points=120_000,
            palette=PaletteGenome(mode="hsl", hue=(0.6, 0.2), sat=0.8, val=0.25),
            render_model="ink", framing="density", glow=0.2, exposure=1.4,
        )],
    )


def test_ink_round_trip_pixel_identical(tmp_path):
    genome = _ink_genome()
    path = genome_io.save(genome, tmp_path / "ink.json")
    reloaded = genome_io.load(path)
    a = np.asarray(Engine().render(genome))
    b = np.asarray(Engine().render(reloaded))
    assert np.array_equal(a, b)


def test_ink_artwork_is_not_uniform():
    """Une encre sur papier doit produire des formes (pas un aplat)."""
    img = np.asarray(Engine().render(_ink_genome())).astype(np.float64)
    assert img.std() > 3.0


def test_generator_can_emit_ink_and_it_renders():
    found = False
    for seed in range(40):
        genome = ag.generate(seed, 128, 128)
        if any(layer.render_model == "ink" for layer in genome.layers):
            img = np.asarray(Engine().render(genome))
            assert img.shape == (128, 128, 3)
            assert img.std() > 1.0  # non uniforme
            found = True
            break
    assert found, "aucune seed n'a produit d'œuvre à l'encre sur 40 essais"


def test_generated_background_reveals_through_empty_areas():
    """Sur un fond non noir, au moins un pixel doit valoir le fond (transparence)."""
    genome = ag.generate(2, 96, 96)
    genome.background = "white"
    genome.background_params = {}
    img = np.asarray(Engine().render(genome))
    # Des zones vides doivent laisser passer le blanc du fond.
    assert (img.min(axis=2) > 240).any()
