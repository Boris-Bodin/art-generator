"""Sérialisation JSON d'un génome.

Une œuvre est enregistrée sous forme d'un fichier JSON auto-suffisant : seed,
génome complet, métadonnées. Le recharger puis le rendre reproduit l'œuvre à
l'identique.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..core.genome import ArtworkGenome, LayerGenome, PaletteGenome


def to_dict(genome: ArtworkGenome) -> dict[str, Any]:
    return asdict(genome)


def _palette_from_dict(d: dict[str, Any]) -> PaletteGenome:
    return PaletteGenome(
        mode=d["mode"],
        offset=tuple(d["offset"]),
        amp=tuple(d["amp"]),
        freq=tuple(d["freq"]),
        phase=tuple(d["phase"]),
    )


def _layer_from_dict(d: dict[str, Any]) -> LayerGenome:
    d = dict(d)
    d["palette"] = _palette_from_dict(d["palette"])
    return LayerGenome(**d)


def from_dict(d: dict[str, Any]) -> ArtworkGenome:
    d = dict(d)
    d["layers"] = [_layer_from_dict(layer) for layer in d["layers"]]
    return ArtworkGenome(**d)


def save(genome: ArtworkGenome, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(genome), indent=2, ensure_ascii=False), "utf-8")
    return path


def load(path: str | Path) -> ArtworkGenome:
    data = json.loads(Path(path).read_text("utf-8"))
    return from_dict(data)
