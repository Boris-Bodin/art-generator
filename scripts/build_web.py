"""Construit les artefacts de l'UI web statique (dossier ``public/``).

L'UI web (voir ``public/index.html``) exécute le moteur **dans le navigateur** via
Pyodide (CPython + numpy + Pillow compilés en WebAssembly). Elle n'a donc besoin
que de trois choses côté build :

* le **wheel** du package (pur-Python), chargé dans Pyodide par ``micropip`` ;
* ``presets.json`` — le catalogue des presets intégrés (nom, fichier, description),
  pour afficher la liste sans attendre le démarrage de Pyodide ;
* ``build.json`` — le nom du wheel produit et la version de Pyodide ciblée, pour
  découpler le front-end du numéro de version.

Le reste du site (``index.html``, ``style.css``, ``app.js``, ``engine.py``) est
écrit à la main et versionné tel quel. Ce script ne régénère que ce qui dépend du
code Python.

Usage ::

    .venv/Scripts/python.exe scripts/build_web.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Version de Pyodide ciblée (doit correspondre au <script> de public/index.html).
# v0.27.2 embarque Python 3.12.7, numpy 2.0.2 et Pillow 10.2.0 — conforme aux
# contraintes de pyproject.toml (python>=3.12, numpy>=2.0, pillow>=10.0).
PYODIDE_VERSION = "v0.27.2"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PUBLIC = ROOT / "public"
VENDOR = PUBLIC / "vendor"

def _build_wheel() -> str:
    """Construit le wheel web sans dépendance matplotlib."""

    VENDOR.mkdir(parents=True, exist_ok=True)

    for old in VENDOR.glob("art_generator-*.whl"):
        old.unlink()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        shutil.copytree(
            ROOT / "art_generator",
            tmp_path / "art_generator",
        )

        shutil.copy(
            ROOT / "pyproject.web.toml",
            tmp_path / "pyproject.toml",
        )

        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                str(tmp_path),
                "--no-deps",
                "-w",
                str(VENDOR),
            ],
            check=True,
        )

    wheels = sorted(VENDOR.glob("art_generator-*.whl"))
    if not wheels:
        raise RuntimeError("Aucun wheel produit dans public/vendor.")

    return wheels[-1].name


def _write_presets() -> int:
    """Écrit ``public/presets.json`` depuis la bibliothèque intégrée."""
    from art_generator.presets import library

    presets = [
        {"name": p.name, "file": p.filename, "description": p.description}
        for p in library.builtin_presets()
    ]
    (PUBLIC / "presets.json").write_text(
        json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(presets)


def _write_build_manifest(wheel: str) -> None:
    """Écrit ``public/build.json`` (nom du wheel + version Pyodide)."""
    manifest = {
        "wheel": f"vendor/{wheel}",
        "pyodide": PYODIDE_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (PUBLIC / "build.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    wheel = _build_wheel()
    n = _write_presets()
    _write_build_manifest(wheel)
    print(f"Wheel     : public/vendor/{wheel}")
    print(f"Presets   : public/presets.json ({n} presets)")
    print(f"Manifeste : public/build.json (Pyodide {PYODIDE_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
