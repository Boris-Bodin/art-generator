"""Moteur de rendu : génome → image.

Orchestration pure. Le moteur ne connaît ni les familles d'équations (il passe
par le registre) ni les détails de rendu (délégués au renderer). Ajouter une
famille, un mode de fusion ou un style de fond ne modifie pas ce fichier.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from ..equations import registry
from ..renderers import accumulation
from . import blend
from .background import make_background
from .genome import ArtworkGenome


class Engine:
    """Reconstruit une œuvre à partir de son :class:`ArtworkGenome`."""

    def render(self, genome: ArtworkGenome) -> Image.Image:
        """Rend le génome et renvoie une image PIL RVB 8 bits."""
        canvas = make_background(genome)

        for layer in genome.layers:
            equation = registry.build(layer.equation_family, layer.equation_params)
            color, alpha = accumulation.render_layer(
                equation, layer, genome.width, genome.height
            )
            canvas = blend.composite(
                canvas, color, alpha, layer.blend_mode, layer.opacity, layer.render_model
            )

        arr = (np.clip(canvas, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")
