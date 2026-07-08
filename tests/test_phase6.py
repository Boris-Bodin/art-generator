"""Tests de la Phase 6 : aperçu, navigation dans l'espace des génomes, presets.

L'UI Tkinter (la *vue*) n'est pas testée ici — elle exige un écran — mais toute
la logique qu'elle orchestre l'est : elle vit dans des modules sans toolkit.
"""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.exporters import genome_io
from art_generator.generators import navigation
from art_generator.main import build_parser
from art_generator.presets import library
from art_generator.ui import preview


def _variance(img) -> float:
    return float(np.asarray(img).astype(float).var())


# --- Aperçu -----------------------------------------------------------------

def test_preview_dimensions_preserve_ratio_and_never_upscale():
    assert preview.preview_dimensions(1600, 1600, max_side=560) == (560, 560)
    assert preview.preview_dimensions(1600, 900, max_side=560) == (560, 315)
    assert preview.preview_dimensions(900, 1600, max_side=560) == (315, 560)
    # déjà plus petit : taille native conservée (pas d'agrandissement)
    assert preview.preview_dimensions(400, 300, max_side=560) == (400, 300)


def test_render_preview_size_and_non_degenerate():
    genome = ag.generate(42, 1600, 1200)
    img = preview.render_preview(genome, max_side=280)
    assert img.size == (280, 210)          # ratio préservé
    assert _variance(img) > 1.0            # image non uniforme (forme visible)


def test_render_preview_does_not_mutate_genome():
    genome = ag.generate(7)
    before = (genome.width, genome.height)
    preview.render_preview(genome, max_side=200)
    assert (genome.width, genome.height) == before


def test_draft_point_cap_speeds_up_without_mutating():
    genome = ag.generate(42)
    original_points = [layer.n_points for layer in genome.layers]
    img = preview.render_preview(genome, max_side=200, point_cap=50_000)
    assert _variance(img) > 1.0                                  # toujours dessinable
    assert [layer.n_points for layer in genome.layers] == original_points  # génome intact


# --- Navigation dans l'espace des génomes -----------------------------------

def test_mutate_is_deterministic():
    genome = ag.generate(3)
    a = navigation.mutate(genome, seed=11)
    b = navigation.mutate(genome, seed=11)
    assert genome_io.to_dict(a) == genome_io.to_dict(b)


def test_mutate_changes_genome_but_preserves_shape():
    genome = ag.generate(3)
    variant = navigation.mutate(genome, seed=11, amount=0.4)
    # le voisin diffère de l'original…
    assert genome_io.to_dict(variant) != genome_io.to_dict(genome)
    # …mais la forme (equation_params) est intacte : viabilité préservée.
    for original, mutated in zip(genome.layers, variant.layers):
        assert mutated.equation_params == original.equation_params
        assert mutated.equation_family == original.equation_family


def test_mutate_does_not_touch_original():
    genome = ag.generate(3)
    snapshot = genome_io.to_dict(genome)
    navigation.mutate(genome, seed=5)
    assert genome_io.to_dict(genome) == snapshot


def test_mutate_round_trips_through_json():
    variant = navigation.mutate(ag.generate(8), seed=2)
    restored = genome_io.from_dict(genome_io.to_dict(variant))
    assert genome_io.to_dict(restored) == genome_io.to_dict(variant)


def test_mutated_genome_still_renders_non_degenerate():
    variant = navigation.mutate(ag.generate(21), seed=99, amount=0.5)
    img = preview.render_preview(variant, max_side=200)
    assert _variance(img) > 1.0


def test_reroll_equations_changes_shape_keeps_staging():
    genome = ag.generate(4)
    variant = navigation.reroll_equations(genome, seed=1)
    changed = any(
        v.equation_params != o.equation_params
        for o, v in zip(genome.layers, variant.layers)
    )
    assert changed
    # la mise en scène (palette, opacité, fond) est conservée.
    assert variant.background == genome.background
    for original, rerolled in zip(genome.layers, variant.layers):
        assert rerolled.opacity == original.opacity
        assert genome_io.to_dict(rerolled.palette) == genome_io.to_dict(original.palette)


def test_reroll_equations_is_deterministic_and_viable():
    genome = ag.generate(4)
    a = navigation.reroll_equations(genome, seed=1)
    b = navigation.reroll_equations(genome, seed=1)
    assert genome_io.to_dict(a) == genome_io.to_dict(b)
    img = preview.render_preview(a, max_side=200)
    assert _variance(img) > 1.0


# --- Bibliothèque de presets ------------------------------------------------

def test_builtin_presets_load_and_are_named():
    names = library.names()
    assert len(names) == len(set(names)) >= 8
    for name in names:
        genome = library.load(name, width=200, height=200)
        assert genome.title == name
        assert genome.width == 200


def test_builtin_presets_render_non_degenerate():
    # échantillon : chaque preset intégré doit produire une image non vide.
    for name in library.names()[:4]:
        img = preview.render_preview(library.load(name), max_side=180)
        assert _variance(img) > 1.0


def test_get_unknown_preset_raises():
    with pytest.raises(KeyError):
        library.get("inexistant")


def test_user_preset_round_trip(tmp_path):
    genome = navigation.mutate(ag.generate(12), seed=3)
    path = library.save_user_preset(genome, "Mon Essai #1", directory=tmp_path)
    assert path.parent == tmp_path
    assert library.list_user_presets(tmp_path) == [path]
    restored = library.load_user_preset(path)
    # Invariant du projet : le round-trip JSON est identique au pixel près (les
    # tuples deviennent des listes en JSON, sans impact sur le rendu).
    original_px = np.asarray(preview.render_preview(genome, max_side=160))
    restored_px = np.asarray(preview.render_preview(restored, max_side=160))
    assert np.array_equal(original_px, restored_px)


def test_user_preset_slugifies_name(tmp_path):
    path = library.save_user_preset(ag.generate(1), "Été : Vague / 2", directory=tmp_path)
    assert path.suffix == ".json"
    assert "/" not in path.stem and ":" not in path.stem


def test_list_user_presets_empty_when_missing(tmp_path):
    assert library.list_user_presets(tmp_path / "nope") == []


# --- CLI --------------------------------------------------------------------

def test_cli_exposes_ui_command():
    parser = build_parser()
    args = parser.parse_args(["ui", "--seed", "42"])
    assert args.seed == 42
    assert args.command == "ui"
