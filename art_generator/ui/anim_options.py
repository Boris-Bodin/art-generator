"""Construction d'une animation depuis des options de haut niveau — logique pure.

L'éditeur graphique propose quelques **effets** cochables (cyclage de couleur,
rotation du fond, particules en comète, flux de bruit) plutôt qu'un éditeur de
pistes brut. Ce module traduit ces options en un génome animé, **sans toolkit** :
il est donc testable sans écran, comme :mod:`ui.preview` et :mod:`ui.param_form`.

:func:`apply` ne mute pas le génome d'entrée : elle renvoie une **copie** dont
``animation`` est peuplé et dont les champs prérequis (``noise_3d``, ``reveal``)
sont posés. Rendre ``evaluate(copie, t)`` produit alors chaque frame.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from ..core.genome import AnimationGenome, ArtworkGenome, Keyframe, Track

_TAU = 6.283185307179586


@dataclass
class AnimationOptions:
    """Réglages d'animation exposés par l'UI."""

    frames: int = 90
    fps: int = 30
    loop: bool = True
    color_cycle: bool = True       # cycle la teinte/phase de chaque couche
    background_spin: bool = True    # fait tourner l'orientation du fond
    particle_reveal: bool = False   # particules qui avancent (queue de comète)
    noise_flow: bool = False        # champ de bruit qui s'écoule (noise_z animé)
    noise_span: float = 3.0         # distance parcourue sur l'axe temporel du bruit


def _color_track(index: int, layer) -> Track:
    """Piste de cyclage couleur adaptée au mode de palette de la couche."""
    if layer.palette.mode in ("hsv", "hsl"):
        h0 = float(layer.palette.hue[0])
        return Track(
            f"layers.{index}.palette.hue.0",
            [Keyframe(0.0, h0), Keyframe(1.0, h0 + 1.0)],
        )
    phase = list(layer.palette.phase)
    return Track(
        f"layers.{index}.palette.phase",
        [Keyframe(0.0, phase), Keyframe(1.0, [p + 1.0 for p in phase])],
    )


def apply(genome: ArtworkGenome, options: AnimationOptions) -> ArtworkGenome:
    """Renvoie une copie de ``genome`` animée selon ``options``.

    Aucun effet coché ⇒ ``animation`` reste ``None`` (œuvre statique). Le génome
    d'entrée n'est jamais modifié.
    """
    g = copy.deepcopy(genome)
    tracks: list[Track] = []

    if options.background_spin:
        tracks.append(
            Track("background_params.angle", [Keyframe(0.0, 0.0), Keyframe(1.0, _TAU)])
        )

    for i, layer in enumerate(g.layers):
        if options.color_cycle:
            tracks.append(_color_track(i, layer))

        if options.particle_reveal and layer.equation_family == "particles":
            layer.equation_params = dict(layer.equation_params)
            layer.equation_params.setdefault("trail", 0.15)
            layer.equation_params["reveal"] = 0.0
            tracks.append(
                Track(
                    f"layers.{i}.equation_params.reveal",
                    [Keyframe(0.0, 0.0), Keyframe(1.0, 1.0)],
                )
            )

        if options.noise_flow and layer.noise_type != "none":
            layer.noise_3d = True
            layer.noise_z = 0.0
            tracks.append(
                Track(
                    f"layers.{i}.noise_z",
                    [Keyframe(0.0, 0.0), Keyframe(1.0, float(options.noise_span))],
                )
            )

    g.animation = (
        AnimationGenome(fps=options.fps, frames=options.frames, loop=options.loop, tracks=tracks)
        if tracks
        else None
    )
    return g
