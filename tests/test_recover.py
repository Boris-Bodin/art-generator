"""Récupération de la seed d'un génome par recherche exhaustive."""

from __future__ import annotations

from art_generator.exporters import genome_io
from art_generator.generators import recover
from art_generator.generators.genome_generator import generate


def test_recover_seed_finds_original():
    target = generate(7)
    result = recover.recover_seed(target, start=0, stop=64)
    assert result.found
    assert result.seed == 7


def test_recover_ignores_seed_title_and_resolution():
    # Un génome dont seed/title sont effacés et la résolution modifiée reste
    # rattachable à sa seed d'origine : ces champs n'influencent aucun tirage.
    target = generate(7)
    target.seed = 0
    target.title = ""
    target.width = target.height = 512
    result = recover.recover_seed(target, start=0, stop=64)
    assert result.seed == 7


def test_recover_survives_json_round_trip(tmp_path):
    path = tmp_path / "g.json"
    genome_io.save(generate(3), path)
    loaded = genome_io.load(path)
    loaded.seed = 0  # simule un JSON dont la seed a été perdue
    assert recover.recover_seed(loaded, start=0, stop=64).seed == 3


def test_recover_returns_none_when_out_of_range():
    target = generate(50)
    result = recover.recover_seed(target, start=0, stop=10)
    assert not result.found
    assert result.seed is None
    assert result.tried == 10
