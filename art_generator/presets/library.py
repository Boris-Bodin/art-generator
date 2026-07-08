"""Bibliothèque de presets (Phase 6).

Deux niveaux :

* **Presets intégrés** — un petit catalogue de seeds curées, chacune nommée et
  décrite. Comme une seed → un génome → une image (invariant du moteur), un preset
  intégré n'a besoin de stocker que sa seed : il se reconstruit à l'identique via
  :func:`~art_generator.generators.genome_generator.generate`. C'est le point de
  départ de la navigation dans l'espace des génomes (:mod:`generators.navigation`).
* **Presets utilisateur** — des génomes *arbitraires* (donc possiblement édités à
  la main dans l'UI, hors de la portée d'une seed) enregistrés en JSON dans un
  dossier dédié, via la sérialisation standard (:mod:`exporters.genome_io`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..core.genome import ArtworkGenome
from ..exporters import genome_io
from ..generators.genome_generator import generate


@dataclass(frozen=True)
class Preset:
    """Preset intégré : une seed nommée et décrite."""

    name: str
    seed: int
    description: str

    def build(self, width: int = 1600, height: int = 1600) -> ArtworkGenome:
        """Reconstruit le génome du preset à la résolution voulue."""
        genome = generate(self.seed, width=width, height=height)
        genome.title = self.name
        return genome


# Catalogue intégré : seeds curées couvrant un éventail de familles et d'ambiances.
# Chaque seed produit une œuvre viable (garanti par le contrôle de qualité).
_BUILTIN: tuple[Preset, ...] = (
    Preset("Aurora", 42, "Voile de lignes lumineuses, palette froide."),
    Preset("Ember", 7, "Attracteur dense aux teintes chaudes."),
    Preset("Nebula", 128, "Nuage étoilé, symétrie radiale."),
    Preset("Tide", 2024, "Champ de vecteurs fluide, dégradé océan."),
    Preset("Filament", 99, "Trajectoires filamentaires fines."),
    Preset("Bloom", 314, "Floraison symétrique en kaléidoscope."),
    Preset("Ink Study", 5, "Encre soustractive sur papier clair."),
    Preset("Vortex", 777, "Tourbillon de particules."),
    Preset("Lattice", 256, "Motif structuré, harmonie complémentaire."),
    Preset("Drift", 1618, "Dérive douce, bruit de warp."),
    Preset("Corona", 88, "Halo radial, forte exposition."),
    Preset("Quartz", 4096, "Facettes nettes, palette minérale."),
)

_BY_NAME: dict[str, Preset] = {p.name: p for p in _BUILTIN}


def builtin_presets() -> tuple[Preset, ...]:
    """Catalogue des presets intégrés."""
    return _BUILTIN


def names() -> list[str]:
    """Noms des presets intégrés (ordre du catalogue)."""
    return [p.name for p in _BUILTIN]


def get(name: str) -> Preset:
    """Preset intégré par son nom."""
    if name not in _BY_NAME:
        raise KeyError(f"Preset inconnu : {name!r}")
    return _BY_NAME[name]


def load(name: str, width: int = 1600, height: int = 1600) -> ArtworkGenome:
    """Raccourci : nom de preset intégré → génome prêt à rendre."""
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
    genome_io.save(genome, path)
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
