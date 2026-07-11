"""Récupération de la seed d'un génome par recherche exhaustive.

La génération ``seed -> génome`` est déterministe mais **non inversible** (l'état
du PCG64 est consommé par des dizaines de tirages). La seule voie pour retrouver
la seed d'un génome dont le champ ``seed`` a été perdu est donc de *re-générer*
les génomes candidats et de les comparer à la cible.

La comparaison ignore les champs qui n'influencent pas les tirages RNG ou qui ne
sont pas déterministes : ``seed`` (l'inconnue), ``title`` (encode la seed),
``created`` (horodatage) et ``width``/``height`` (n'affectent aucun tirage — une
seed reste donc trouvable même si l'œuvre a été re-cadrée à une autre résolution).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.genome import ArtworkGenome
from ..exporters import genome_io
from . import genome_generator

# Champs volontairement exclus de la comparaison structurelle.
_IGNORED_FIELDS = ("seed", "title", "created", "width", "height")


def _fingerprint(genome: ArtworkGenome) -> dict[str, Any]:
    """Représentation canonique d'un génome, indépendante de la seed/résolution."""
    d = genome_io.to_dict(genome)
    for key in _IGNORED_FIELDS:
        d.pop(key, None)
    return d


@dataclass
class RecoveryResult:
    """Issue d'une recherche de seed."""

    seed: int | None
    tried: int

    @property
    def found(self) -> bool:
        return self.seed is not None


def recover_seed(
    target: ArtworkGenome,
    start: int = 0,
    stop: int = 100_000,
    on_progress: Any = None,
) -> RecoveryResult:
    """Cherche dans ``[start, stop)`` une seed reproduisant ``target``.

    Retourne la première seed dont le génome régénéré est structurellement
    identique à la cible (champs non déterministes exclus), ou ``None`` si aucune
    seed de l'intervalle ne convient. ``on_progress(seed)`` est appelé
    périodiquement pour le suivi, s'il est fourni.
    """
    reference = _fingerprint(target)
    for seed in range(start, stop):
        if on_progress is not None and seed % 5_000 == 0:
            on_progress(seed)
        candidate = genome_generator.generate(seed)
        if _fingerprint(candidate) == reference:
            return RecoveryResult(seed=seed, tried=seed - start + 1)
    return RecoveryResult(seed=None, tried=stop - start)
