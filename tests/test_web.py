"""Tests de l'UI web (dossier ``public/``), exécutés dans pytest.

Historiquement, seule l'étape de *build* (``scripts/build_web.py``) touchait au
web : une régression du point d'entrée navigateur (``public/engine.py``) ou une
dérive de version Pyodide ne se voyait qu'au déploiement. Ces tests valident donc
directement les artefacts web côté CPython, en amont du build :

* ``public/engine.py`` rend réellement un preset et une seed (il importe le vrai
  package ; seul le pont de types diffère du natif) ;
* son catalogue ``presets_json()`` reste cohérent avec la bibliothèque intégrée
  et avec ce que le build recopiera dans ``presets.json`` ;
* la version Pyodide de ``index.html`` correspond à celle du script de build.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from art_generator.presets import library

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _web_engine():
    """Charge ``public/engine.py`` en bridant taille et points pour un test vif."""
    engine = _load_module(PUBLIC / "engine.py", "web_engine")
    engine.WEB_MAX_SIDE = 200
    engine.WEB_POINT_CAP = 40_000
    return engine


def _decode_png(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def _variance(img: Image.Image) -> float:
    return float(np.asarray(img).astype(float).var())


def test_web_engine_renders_seed_to_png():
    engine = _web_engine()
    img = _decode_png(engine.render_seed(42))
    assert img.format == "PNG"
    assert _variance(img) > 1.0  # image non uniforme


def test_web_engine_renders_first_builtin_preset():
    engine = _web_engine()
    name = library.builtin_presets()[0].name
    img = _decode_png(engine.render_preset(name))
    assert _variance(img) > 1.0


def test_web_presets_json_matches_library():
    engine = _web_engine()
    from_web = json.loads(engine.presets_json())
    expected = [
        {"name": p.name, "file": p.filename, "description": p.description}
        for p in library.builtin_presets()
    ]
    assert from_web == expected


def test_build_script_presets_json_matches_web_engine(tmp_path):
    # Le presets.json écrit par le build et le catalogue exposé au navigateur
    # doivent coïncider : sinon la liste affichée se désynchronise du moteur.
    build = _load_module(ROOT / "scripts" / "build_web.py", "build_web")
    build.PUBLIC = tmp_path
    build._write_presets()
    written = json.loads((tmp_path / "presets.json").read_text(encoding="utf-8"))
    assert written == json.loads(_web_engine().presets_json())


def test_index_html_pyodide_version_matches_build_script():
    build = _load_module(ROOT / "scripts" / "build_web.py", "build_web")
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    versions = set(re.findall(r"pyodide/(v[\d.]+)/", html))
    assert versions, "aucune référence Pyodide dans index.html"
    assert versions == {build.PYODIDE_VERSION}
