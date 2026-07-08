"""Tests de la Phase 5 : résolutions/ratio, rendu par tuiles, export vectoriel."""

from __future__ import annotations

import xml.dom.minidom as minidom

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.background import make_background
from art_generator.core.engine import Engine
from art_generator.core.genome import ArtworkGenome, LayerGenome
from art_generator.exporters import vector
from art_generator.exporters.resolution import (
    PRESETS,
    parse_ratio,
    resolve_dimensions,
)


# --- 5b : résolutions & rapport d'aspect ------------------------------------

def test_preset_long_edge_and_ratio():
    assert resolve_dimensions("4k", "16:9") == (3840, 2160)
    assert resolve_dimensions("8k") == (7680, 7680)  # 1:1 par défaut
    # ratio portrait : le grand côté va à la hauteur
    assert resolve_dimensions("4k", "4:5") == (3072, 3840)


def test_size_is_long_edge_with_ratio():
    assert resolve_dimensions(size=800) == (800, 800)
    assert resolve_dimensions(size=800, ratio="3:2") == (800, 533)
    assert resolve_dimensions() == (1600, 1600)  # défaut


def test_parse_ratio_forms():
    assert parse_ratio("16:9") == (16.0, 9.0)
    assert parse_ratio("3/2") == (3.0, 2.0)
    assert parse_ratio("1.5") == (1.5, 1.0)


def test_unknown_preset_and_bad_ratio_raise():
    with pytest.raises(ValueError):
        resolve_dimensions("5k")
    with pytest.raises(ValueError):
        parse_ratio("16:0")


def test_all_presets_resolve():
    for name in PRESETS:
        w, h = resolve_dimensions(name, "16:9")
        assert w >= h > 0


def test_preset_carries_its_own_ratio():
    # displate impose son format portrait (1:1.4) sans --ratio explicite.
    assert resolve_dimensions("displate") == (4000, 5600)
    # un --ratio explicite prime sur le ratio du préréglage.
    assert resolve_dimensions("displate", "16:9") == (5600, 3150)
    # un préréglage sans ratio propre reste carré par défaut.
    assert resolve_dimensions("4k") == (3840, 3840)


# --- 5b : rendu par tuiles ---------------------------------------------------

def _small_genome(seed=777, w=300, h=300):
    return ag.generate(seed, w, h)


def test_tiled_is_pixel_identical_to_single():
    """Le rendu par tuiles doit reproduire le chemin simple au pixel près."""
    genome = _small_genome()
    engine = Engine()
    single = np.asarray(engine.render(genome, tile="off"))
    tiled = np.asarray(engine.render(genome, tile=64))
    assert np.array_equal(single, tiled)


def test_tiled_identical_across_band_heights():
    genome = _small_genome(seed=101)
    engine = Engine()
    a = np.asarray(engine.render(genome, tile=37))   # bande ne divisant pas 300
    b = np.asarray(engine.render(genome, tile=128))
    assert np.array_equal(a, b)


def test_auto_tiling_threshold():
    small = ArtworkGenome(width=1000, height=1000, layers=[])
    huge = ArtworkGenome(width=8000, height=8000, layers=[])
    assert not Engine._use_tiling(small, None)
    assert Engine._use_tiling(huge, None)
    assert Engine._use_tiling(small, 64)      # forcé
    assert not Engine._use_tiling(huge, "off")  # désactivé


def test_non_square_render_matches_dimensions():
    genome = ag.generate(9, 320, 240)
    img = Engine().render(genome, tile=50)
    assert img.size == (320, 240)


# --- 5b : indépendance à la résolution (densité constante) -------------------

def test_scale_floored_at_reference():
    # En deçà / à la référence : scale = 1 (rendu inchangé) ; au-delà : > 1.
    assert Engine._scale(ArtworkGenome(width=800, height=800)) == 1.0
    assert Engine._scale(ArtworkGenome(width=1600, height=1600)) == 1.0
    assert Engine._scale(ArtworkGenome(width=3200, height=3200)) == 2.0
    assert Engine._scale(ArtworkGenome(width=3200, height=1800)) > 1.0


def test_stroke_scale_is_per_family():
    from art_generator.renderers.accumulation import _stroke_scale
    # Familles filamentaires : épaisseur/glow suivent la résolution.
    assert _stroke_scale("vector_field", 2.0) == 2.0
    assert _stroke_scale("parametric", 3.0) == 3.0
    assert _stroke_scale("polar", 2.0) == 2.0
    assert _stroke_scale("complex", 2.0) == 2.0
    # Familles nuage : traits fins et nets (pas de mise à l'échelle du trait).
    assert _stroke_scale("attractor", 2.0) == 1.0
    assert _stroke_scale("particles", 2.0) == 1.0
    assert _stroke_scale("fractal", 2.0) == 1.0


def test_density_is_resolution_independent():
    """Même seed à deux résolutions ≥ référence : la part de fond reste stable.

    C'est la correction du symptôme « plus de fond apparaît en montant en
    résolution » : le nombre de points croît avec l'aire pour garder la densité
    par pixel constante.
    """
    def background_fraction(size):
        g = ag.generate(42, size, size)
        g.background, g.background_params = "black", {}
        lum = np.asarray(Engine().render(g, tile="off")).astype(float).mean(axis=2)
        return (lum < 8).mean()

    ref = background_fraction(1600)   # scale = 1
    big = background_fraction(2560)   # scale = 1.6
    assert abs(ref - big) < 0.05      # densités quasi identiques (< 5 pts de %)


# --- 5b : fonds par bandes (base du rendu par tuiles) ------------------------

@pytest.mark.parametrize("background,params", [
    ("gradient", {"top": (0.9, 0.1, 0.2), "bottom": (0.0, 0.0, 0.3)}),
    ("gradient", {"top": (0.9, 0.1, 0.2), "bottom": (0.0, 0.0, 0.3), "angle": 35.0}),
    ("radial", {"inner": (1.0, 1.0, 1.0), "outer": (0.0, 0.0, 0.0), "vignette": 0.4}),
    ("white", {"vignette": 0.5}),
])
def test_banded_background_matches_full(background, params):
    genome = ArtworkGenome(width=41, height=53, background=background,
                           background_params=params, layers=[])
    full = make_background(genome)
    bands = np.vstack([make_background(genome, y0, min(53, y0 + 13))
                       for y0 in range(0, 53, 13)])
    assert np.array_equal(full, bands)


# --- 5a : export vectoriel SVG/PDF -------------------------------------------

def test_svg_export_is_valid_vector(tmp_path):
    genome = ag.generate(42, 400, 300)
    path = vector.save_vector(genome, tmp_path / "art.svg", dpi=150, max_points=2000)
    assert path.exists() and path.stat().st_size > 0
    doc = minidom.parse(str(path))
    assert doc.documentElement.tagName == "svg"
    # Tracés vectoriels présents (matplotlib factorise les points en defs + <use>).
    marks = doc.getElementsByTagName("use") + doc.getElementsByTagName("path")
    assert len(marks) > 0


def test_pdf_export_writes_file(tmp_path):
    genome = ag.generate(3, 300, 300)
    path = vector.save_vector(genome, tmp_path / "art.pdf", dpi=150, max_points=2000)
    assert path.exists()
    assert path.read_bytes()[:5] == b"%PDF-"


def test_vector_subsample_is_capped_and_deterministic():
    idx1 = vector._subsample(100_000, 1500, seed=11)
    idx2 = vector._subsample(100_000, 1500, seed=11)
    assert len(idx1) == 1500
    assert np.array_equal(idx1, idx2)          # reproductible (RNG déterministe)
    assert np.array_equal(idx1, np.sort(idx1))  # trié (préserve l'ordre du tracé)
    # Sous le plafond : tous les points sont conservés.
    assert np.array_equal(vector._subsample(500, 1500, seed=0), np.arange(500))


def test_vector_background_color_choice():
    assert vector._background_color(ArtworkGenome(background="white")) == (1.0, 1.0, 1.0)
    assert vector._background_color(ArtworkGenome(background="black")) == (0.0, 0.0, 0.0)
