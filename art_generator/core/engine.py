"""Moteur de rendu : génome → image.

Orchestration pure. Le moteur ne connaît ni les familles d'équations (il passe
par le registre) ni les détails de rendu (délégués au renderer). Ajouter une
famille, un mode de fusion ou un style de fond ne modifie pas ce fichier.

Deux chemins de rendu, à sortie **identique au pixel près** :

* le chemin **simple** matérialise l'image entière d'un bloc (petites et
  moyennes tailles) ;
* le chemin **par tuiles** (Phase 5) compose l'image bande par bande pour borner
  la mémoire aux très grandes résolutions (8K/16K) — un tampon HDR 16K en
  float64 pèserait plusieurs gigaoctets par couche.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from ..equations import registry
from ..renderers import accumulation
from . import blend
from .background import make_background
from .genome import ArtworkGenome

# Au-delà de ce côté (px), on bascule automatiquement en rendu par tuiles.
_AUTO_TILE_ABOVE = 4096
# Hauteur de bande par défaut (px) et halo pour que le glow reste continu aux
# coutures des bandes (le halo est calculé puis rogné).
_DEFAULT_TILE_HEIGHT = 512
_HALO = 32
# Côté de référence (px) pour l'indépendance à la résolution : c'est la taille
# par défaut pour laquelle le générateur calibre la densité de points. À cette
# taille (ou en deçà) le rendu est **inchangé** au pixel près ; au-delà, le
# nombre de points croît avec l'**aire** pour garder la densité par pixel — donc
# la part de fond — constante (fin du « plus de fond apparaît en montant en
# résolution »). L'épaisseur et le glow ne sont mis à l'échelle que pour les
# familles filamentaires (voir accumulation._stroke_scale) ; les familles nuage
# gardent des traits fins et nets.
_REFERENCE_EDGE = 1600


class Engine:
    """Reconstruit une œuvre à partir de son :class:`ArtworkGenome`."""

    def render(self, genome: ArtworkGenome, tile: int | str | None = None) -> Image.Image:
        """Rend le génome et renvoie une image PIL RVB 8 bits.

        ``tile`` pilote le rendu par tuiles :

        * ``None`` / ``"auto"`` — bascule automatique selon la taille de l'image ;
        * ``"off"`` / ``0`` — force le chemin simple d'un bloc ;
        * entier ``> 0`` — force le rendu par tuiles avec cette hauteur de bande.
        """
        if self._use_tiling(genome, tile):
            return self._render_tiled(genome, self._tile_height(genome, tile))
        return self._render_single(genome)

    # -- chemin simple (historique) ------------------------------------------

    def _render_single(self, genome: ArtworkGenome) -> Image.Image:
        canvas = make_background(genome)
        scale = self._scale(genome)

        for layer in genome.layers:
            equation = registry.build(layer.equation_family, layer.equation_params)
            color, alpha = accumulation.render_layer(
                equation, layer, genome.width, genome.height, scale
            )
            canvas = blend.composite(
                canvas, color, alpha, layer.blend_mode, layer.opacity, layer.render_model
            )

        arr = (np.clip(canvas, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")

    # -- chemin par tuiles (Phase 5) -----------------------------------------

    def _render_tiled(self, genome: ArtworkGenome, tile_height: int) -> Image.Image:
        """Compose l'image bande par bande à mémoire bornée.

        Chaque couche est projetée **une fois** en un nuage de points compact
        (`project_layer`). Une pré-passe cumule la densité globale pour figer le
        percentile de normalisation (`global_hi`) — identique au chemin simple.
        Puis, pour chaque bande, on ré-accumule uniquement les points concernés
        (bande élargie d'un halo pour un glow continu), on résout et on compose.
        """
        h, w = genome.height, genome.width
        scale = self._scale(genome)
        # Le halo doit couvrir le rayon effectif du glow (jusqu'à 6·scale pour les
        # familles filamentaires) pour rester continu aux coutures : ~3σ + marge.
        halo = max(_HALO, 3 * max(1, round(6 * scale)) + 8)

        prepared = []  # (layer, coords, colors, weight, radius, hi)
        for layer in genome.layers:
            equation = registry.build(layer.equation_family, layer.equation_params)
            coords, colors, weight, radius = accumulation.project_layer(equation, layer, w, h, scale)
            if len(coords) == 0:
                prepared.append(None)
                continue
            # Densité globale (float64, transitoire) → percentile exact, puis libérée.
            _, acc_w = accumulation.accumulate(coords, None, weight, radius, w, 0, h)
            hi = accumulation.global_hi(acc_w, layer)
            del acc_w
            prepared.append((layer, coords, colors, weight, radius, hi))

        out = np.empty((h, w, 3), dtype=np.uint8)
        for y0 in range(0, h, tile_height):
            y1 = min(h, y0 + tile_height)
            ya = max(0, y0 - halo)
            yb = min(h, y1 + halo)

            band = make_background(genome, ya, yb)
            for item in prepared:
                if item is None:
                    continue
                layer, coords, colors, weight, radius, hi = item
                acc_col, acc_w = accumulation.accumulate(coords, colors, weight, radius, w, ya, yb)
                stroke = accumulation._stroke_scale(layer.equation_family, scale)
                color, alpha = accumulation._resolve(acc_col, acc_w, layer, hi=hi, scale=stroke)
                band = blend.composite(
                    band, color, alpha, layer.blend_mode, layer.opacity, layer.render_model
                )

            top = y0 - ya
            visible = band[top : top + (y1 - y0)]
            out[y0:y1] = (np.clip(visible, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)

        return Image.fromarray(out, mode="RGB")

    # -- indépendance à la résolution ----------------------------------------

    @staticmethod
    def _scale(genome: ArtworkGenome) -> float:
        """Facteur linéaire de résolution (≥ 1) par rapport au côté de référence.

        Basé sur la moyenne géométrique des dimensions pour être neutre au ratio.
        Planché à 1.0 : en deçà de la référence, le rendu reste identique à
        l'historique (aucune régression, densité inchangée).
        """
        return max(1.0, (genome.width * genome.height) ** 0.5 / _REFERENCE_EDGE)

    # -- décision & réglage du tiling ----------------------------------------

    @staticmethod
    def _use_tiling(genome: ArtworkGenome, tile: int | str | None) -> bool:
        if tile in (None, "auto"):
            return max(genome.width, genome.height) > _AUTO_TILE_ABOVE
        if tile in ("off", 0, "0"):
            return False
        return int(tile) > 0

    @staticmethod
    def _tile_height(genome: ArtworkGenome, tile: int | str | None) -> int:
        if isinstance(tile, int) and tile > 0:
            return min(tile, genome.height)
        if isinstance(tile, str) and tile.isdigit() and int(tile) > 0:
            return min(int(tile), genome.height)
        return min(_DEFAULT_TILE_HEIGHT, genome.height)
