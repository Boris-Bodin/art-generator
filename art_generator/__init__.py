"""Moteur d'art génératif mathématique.

API de haut niveau :

    >>> import art_generator as ag
    >>> genome = ag.generate(seed=42)
    >>> image = ag.Engine().render(genome)
    >>> image.save("oeuvre.png")

Une œuvre est entièrement définie par son :class:`ArtworkGenome`, lui-même
reconstruit depuis une seed. Voir ``art_generator.main`` pour l'interface ligne
de commande.
"""

from __future__ import annotations

from .core.engine import Engine
from .core.genome import ArtworkGenome, LayerGenome, PaletteGenome
from .generators.genome_generator import generate

__all__ = [
    "Engine",
    "ArtworkGenome",
    "LayerGenome",
    "PaletteGenome",
    "generate",
    "render_seed",
]

__version__ = "0.1.0"


def render_seed(seed: int, width: int = 1600, height: int = 1600):
    """Raccourci : ``seed`` → (génome, image PIL)."""
    genome = generate(seed, width=width, height=height)
    image = Engine().render(genome)
    return genome, image
