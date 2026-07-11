"""Tests de l'aperçu, de la navigation dans l'espace des génomes et des presets.

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
from art_generator.ui.app import _layer_label
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
    names = [preset.name for preset in library.builtin_presets()]
    assert len(names) >= 1
    for name in names:
        genome = library.load(name, width=200, height=200)
        assert genome.title == name
        assert genome.width == 200
        assert genome.height == 200


def test_builtin_presets_are_loaded_from_json_files():
    preset = library.get("Abstract Purple Particle Mandala")
    genome = preset.build(width=320, height=180)
    assert preset.filename == "abstract_purple_particle_mandala.json"
    assert genome.seed == 1947328337
    assert genome.width == 320
    assert genome.height == 180
    assert genome.layers[0].equation_params["variant"] == "julia"


def test_builtin_presets_render_non_degenerate():
    # échantillon : chaque preset intégré doit produire une image non vide.
    for name in [preset.name for preset in library.builtin_presets()][:4]:
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


def test_saved_user_preset_is_discovered_by_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "default_dir", lambda: tmp_path)
    library.save_user_preset(ag.generate(9), "Preset visible")
    assert "Preset visible" in library.names()
    genome = library.load("Preset visible", width=120, height=80)
    assert genome.title == "Preset visible"
    assert genome.width == 120
    assert genome.height == 80


def test_builtin_dir_points_to_presets_package():
    # Le dossier ciblé pour livrer un preset est bien le package versionné,
    # celui d'où proviennent les presets intégrés.
    directory = library.builtin_dir()
    assert directory.name == "presets"
    assert (directory / "library.py").exists()
    for preset in library.builtin_presets():
        assert preset.path.parent == directory


def test_save_builtin_preset_writes_into_package(tmp_path, monkeypatch):
    # save_builtin_preset délègue à builtin_dir() : on l'y détourne pour ne pas
    # polluer le package, et on vérifie que le preset y est écrit puis découvert
    # par le catalogue intégré.
    monkeypatch.setattr(library, "builtin_dir", lambda: tmp_path)
    path = library.save_builtin_preset(ag.generate(9), "Preset livré")
    assert path.parent == tmp_path
    assert "Preset livré" in [p.name for p in library.builtin_presets()]


def test_user_preset_slugifies_name(tmp_path):
    path = library.save_user_preset(ag.generate(1), "Été : Vague / 2", directory=tmp_path)
    assert path.suffix == ".json"
    assert "/" not in path.stem and ":" not in path.stem


def test_list_user_presets_empty_when_missing(tmp_path):
    assert library.list_user_presets(tmp_path / "nope") == []


def test_layer_label_includes_family_variant_and_symmetry():
    layer = ag.LayerGenome(
        equation_family="attractor",
        equation_params={"variant": "clifford"},
        symmetry="kaleidoscope",
        symmetry_order=8,
    )
    label = _layer_label(layer, 0, 3)
    assert label == "1. attractor · clifford · kaleidoscope x8 (1/3)"


def test_layer_label_avoids_duplicate_family_name():
    vector = ag.LayerGenome(
        equation_family="vector_field",
        equation_params={"seed": 123},
    )
    particles = ag.LayerGenome(
        equation_family="particles",
        equation_params={"emitter": {"type": "ring"}},
    )
    assert _layer_label(vector, 0, 2) == "1. vector_field · flow seed 123 (1/2)"
    assert _layer_label(particles, 1, 2) == "2. particles · emitter ring (2/2)"


# --- CLI --------------------------------------------------------------------

def test_cli_exposes_ui_command():
    parser = build_parser()
    args = parser.parse_args(["ui", "--seed", "42"])
    assert args.seed == 42
    assert args.command == "ui"
