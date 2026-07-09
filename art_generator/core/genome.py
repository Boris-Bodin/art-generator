"""Génome mathématique d'une œuvre.

Une œuvre est *entièrement* définie par son :class:`ArtworkGenome`. À partir de
cette structure (et donc de la seed qui la génère), une œuvre est reproductible
au pixel près. Le génome est un pur conteneur de données : aucune logique de
rendu n'y est présente, ce qui le rend trivial à sérialiser en JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PaletteGenome:
    """Palette procédurale de type gradient cosinus (Inigo Quilez).

    Chaque canal ``c`` est calculé, pour une valeur ``t`` dans ``[0, 1]`` :

        c(t) = offset[c] + amp[c] * cos(2*pi * (freq[c] * t + phase[c]))

    Ce modèle produit des dégradés cycliques doux qui donnent aux œuvres d'une
    même famille une parenté chromatique reconnaissable.
    """

    mode: str = "cosine"  # cosine | hsv | hsl | gradient
    name: str = ""  # nom de palette / schéma d'harmonie (traçabilité, facultatif)
    # --- mode cosinus ---
    offset: tuple[float, float, float] = (0.5, 0.5, 0.5)
    amp: tuple[float, float, float] = (0.5, 0.5, 0.5)
    freq: tuple[float, float, float] = (1.0, 1.0, 1.0)
    phase: tuple[float, float, float] = (0.0, 0.33, 0.67)
    # --- mode HSV (teinte parcourue le long de t) ---
    hue: tuple[float, float] = (0.0, 1.0)  # (départ, amplitude)
    sat: float = 0.7
    val: float = 1.0
    # --- mode dégradé multi-arrêts : liste d'arrêts (position, r, g, b) ---
    stops: list | None = None


@dataclass
class LayerGenome:
    """Génome d'une couche. Une œuvre est composée de plusieurs couches.

    Chaque couche possède sa propre équation, sa palette, son mode de fusion et
    son opacité, conformément à la philosophie « une œuvre = un empilement ».
    """

    equation_family: str = "attractor"
    equation_params: dict[str, Any] = field(default_factory=dict)

    n_points: int = 200_000

    palette: PaletteGenome = field(default_factory=PaletteGenome)
    color_by: str = "velocity"  # 'velocity' | 't' | 'radius'

    blend_mode: str = "add"  # normal | add | screen | multiply | difference
    opacity: float = 1.0

    # --- modèle de rendu ---
    # 'light' : light painting additif (le pigment ajoute de la lumière) ;
    # 'ink'   : encre soustractive (le pigment assombrit le support).
    render_model: str = "light"  # light | ink
    # Cadrage de la couche : 'box' = milieu de la boîte des percentiles (robuste,
    # historique) ; 'density' = centroïde pondéré par la densité (cœur de la forme).
    framing: str = "box"  # box | density

    thickness: float = 1.0
    glow: float = 0.6
    exposure: float = 1.0

    symmetry: str = "none"  # none | mirror | radial | kaleidoscope
    symmetry_order: int = 6

    # --- déformation par bruit ---
    noise_type: str = "none"  # none | perlin | simplex | fbm | worley
    warp: float = 0.0  # amplitude de déformation du domaine (coordonnées)
    warp_freq: float = 1.5  # fréquence spatiale du bruit de warp
    color_noise: float = 0.0  # modulation des valeurs de coloration par le bruit
    light_noise: float = 0.0  # modulation de la luminosité par point (0 = aucune)
    thickness_noise: float = 0.0  # épaisseur additionnelle max (px) pilotée par bruit
    noise_seed: int = 0


@dataclass
class ArtworkGenome:
    """Génome complet d'une œuvre.

    Regroupe les paramètres globaux (seed, dimensions, fond) et la liste des
    couches. Se sérialise/désérialise via :mod:`art_generator.exporters.genome_io`.
    """

    seed: int = 0
    width: int = 1600
    height: int = 1600

    background: str = "black"  # black | white | gradient | radial
    background_params: dict[str, Any] = field(default_factory=dict)

    layers: list[LayerGenome] = field(default_factory=lambda: [LayerGenome()])

    title: str = ""
    comment: str = ""
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
