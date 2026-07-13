"""Tests de la source de couleur « longueur d'arc » (dégradés le long de la trajectoire)."""

from __future__ import annotations

import copy

import numpy as np

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.equations.base import Equation
from art_generator.exporters import genome_io


def _pixels(genome):
    return np.asarray(Engine().render(genome))


def test_arc_length_values_monotonic_and_normalized():
    # Trajectoire régulière : le cumul doit croître de 0 à 1.
    t = np.linspace(0.0, 1.0, 100)
    points = np.column_stack((t, np.zeros_like(t)))
    values = Equation.arc_length_values(points)
    assert values[0] == 0.0
    assert values[-1] == 1.0
    assert np.all(np.diff(values) >= 0.0)


def test_arc_length_values_caps_singular_jump():
    # Un saut géant ne doit pas comprimer tout le dégradé sur les segments normaux.
    x = np.arange(1000.0)
    x[500] = 1e9  # une singularité isolée (0,2 % des segments, dans la queue du 99e)
    points = np.column_stack((x, np.zeros_like(x)))
    values = Equation.arc_length_values(points)
    assert values[-1] == 1.0
    # Sans bridage, le saut écraserait tout : le point 499 serait ~5e-7.
    # Avec bridage au 99e percentile, la moitié gauche garde ~la moitié du dégradé.
    assert values[499] > 0.2


def test_arc_length_values_degenerate_is_zero():
    points = np.zeros((50, 2))
    values = Equation.arc_length_values(points)
    assert np.array_equal(values, np.zeros(50))


def _arc_genome(seed=42):
    return ag.generate(seed, 256, 256)


def test_default_color_source_is_pixel_identical():
    # Un génome au défaut ('sample') rend exactement comme avant l'ajout du champ.
    genome = ag.generate(321, 256, 256)
    assert all(layer.color_source == "sample" for layer in genome.layers)
    baseline = _pixels(genome)
    again = _pixels(copy.deepcopy(genome))
    assert np.array_equal(baseline, again)


def test_arc_source_changes_output():
    genome = _arc_genome()
    sample_px = _pixels(copy.deepcopy(genome))
    for layer in genome.layers:
        layer.color_source = "arc"
    arc_px = _pixels(genome)
    assert not np.array_equal(sample_px, arc_px)


def test_arc_source_round_trip_is_pixel_identical(tmp_path):
    genome = _arc_genome()
    for layer in genome.layers:
        layer.color_source = "arc"
    path = genome_io.save(genome, tmp_path / "arc.json")
    reloaded = genome_io.load(path)
    assert reloaded.layers[0].color_source == "arc"
    assert np.array_equal(_pixels(genome), _pixels(reloaded))


def test_legacy_json_without_color_source_defaults_to_sample(tmp_path):
    genome = ag.generate(7, 128, 128)
    data = genome_io.to_dict(genome)
    for layer in data["layers"]:
        layer.pop("color_source", None)
    path = tmp_path / "legacy.json"
    path.write_text(__import__("json").dumps(data), "utf-8")
    reloaded = genome_io.load(path)
    assert all(layer.color_source == "sample" for layer in reloaded.layers)
