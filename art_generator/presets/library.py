"""Bibliothèque de presets.

Deux niveaux :

* **Presets intégrés** — un petit catalogue de génomes JSON curés, chacun nommé
  et décrit. Ils passent par la même sérialisation que les œuvres utilisateur, ce
  qui permet de livrer des presets réellement édités plutôt que de simples seeds.
* **Presets utilisateur** — des génomes *arbitraires* (donc possiblement édités à
  la main dans l'UI, hors de la portée d'une seed) enregistrés en JSON dans un
  dossier dédié, via la sérialisation standard (:mod:`exporters.genome_io`).
"""

from __future__ import annotations

import re
import copy
from dataclasses import dataclass
from pathlib import Path

from ..core.genome import ArtworkGenome
from ..exporters import genome_io


@dataclass(frozen=True)
class Preset:
    """Preset JSON nommé et décrit."""

    name: str
    path: Path
    description: str

    @property
    def filename(self) -> str:
        """Nom du fichier, pour les manifests web et les tests."""
        return self.path.name

    def build(self, width: int = 1600, height: int = 1600) -> ArtworkGenome:
        """Reconstruit le génome du preset à la résolution voulue."""
        genome = genome_io.load(self.path)
        genome.width = width
        genome.height = height
        genome.title = self.name
        return genome


def _builtin_dir() -> Path:
    """Dossier contenant les presets JSON embarqués dans le package."""
    return Path(__file__).resolve().parent


def _preset_from_path(path: Path) -> Preset:
    genome = genome_io.load(path)
    title = genome.title.strip()
    if title and title != path.stem:
        name = title
    else:
        name = path.stem.replace("_", " ").capitalize()
    description = genome.comment.strip() if genome.comment else f"Preset JSON : {path.name}"
    return Preset(name=name, path=path, description=description)


def _load_presets_from(directory: Path) -> tuple[Preset, ...]:
    """Charge les presets JSON d'un dossier."""
    if not directory.exists():
        return ()
    return tuple(_preset_from_path(path) for path in sorted(directory.glob("*.json")))


def builtin_presets() -> tuple[Preset, ...]:
    """Catalogue des presets embarqués dans le package."""
    return _load_presets_from(_builtin_dir())


def user_presets(directory: str | Path | None = None) -> tuple[Preset, ...]:
    """Catalogue des presets utilisateur."""
    directory = Path(directory) if directory is not None else default_dir()
    return _load_presets_from(directory)


def presets(directory: str | Path | None = None) -> tuple[Preset, ...]:
    """Catalogue des presets JSON disponibles pour l'UI."""
    found: dict[str, Preset] = {}
    for preset in (*builtin_presets(), *user_presets(directory)):
        found.setdefault(preset.name, preset)
    return tuple(found.values())


def names() -> list[str]:
    """Noms des presets disponibles."""
    return [p.name for p in presets()]


def get(name: str) -> Preset:
    """Preset par son nom."""
    by_name = {p.name: p for p in presets()}
    if name not in by_name:
        raise KeyError(f"Preset inconnu : {name!r}")
    return by_name[name]


def load(name: str, width: int = 1600, height: int = 1600) -> ArtworkGenome:
    """Raccourci : nom de preset → génome prêt à rendre."""
    return get(name).build(width=width, height=height)


# --- Presets utilisateur (génomes arbitraires sur disque) -------------------


def default_dir() -> Path:
    """Dossier par défaut des presets utilisateur (``~/.art_generator/presets``)."""
    return Path.home() / ".art_generator" / "presets"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", name.strip().lower()).strip("_")
    return slug or "preset"


def save_user_preset(
    genome: ArtworkGenome, name: str, directory: str | Path | None = None
) -> Path:
    """Enregistre un génome comme preset utilisateur (JSON) et renvoie son chemin."""
    directory = Path(directory) if directory is not None else default_dir()
    path = directory / f"{_slugify(name)}.json"
    saved = copy.deepcopy(genome)
    saved.title = name
    genome_io.save(saved, path)
    return path


def list_user_presets(directory: str | Path | None = None) -> list[Path]:
    """Liste triée des fichiers de presets utilisateur d'un dossier."""
    directory = Path(directory) if directory is not None else default_dir()
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


def load_user_preset(path: str | Path) -> ArtworkGenome:
    """Charge un preset utilisateur depuis son fichier JSON."""
    return genome_io.load(path)
