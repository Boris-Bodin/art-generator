"""Contrats statiques de l'UI web."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"


def test_web_preset_manifest_matches_file_backed_presets():
    from art_generator.presets import library

    data = json.loads((PUBLIC / "presets.json").read_text("utf-8"))
    expected = [
        {"name": p.name, "file": p.filename, "description": p.description}
        for p in library.builtin_presets()
    ]
    assert data == expected
    assert all((ROOT / "art_generator" / "presets" / item["file"]).exists() for item in data)


def test_web_entrypoints_are_wired():
    index = (PUBLIC / "index.html").read_text("utf-8")
    app = (PUBLIC / "app.js").read_text("utf-8")
    engine = (PUBLIC / "engine.py").read_text("utf-8")

    assert 'id="btn-random"' in index
    assert 'id="preset-list"' in index
    assert "fetch(\"presets.json\")" in app
    assert "render_preset" in app
    assert "def render_preset" in engine
    assert "def render_seed" in engine
