"""Résolutions de sortie : préréglages, rapport d'aspect, dimensions.

Le génome ne connaît que ``width``/``height`` en pixels. Ce module traduit des
intentions de haut niveau (« 4K en 16:9 ») en un couple ``(width, height)`` que
l'on injecte dans le génome avant rendu. Le grand côté du préréglage est assigné
à la plus grande dimension du rapport d'aspect ; l'orientation suit le rapport.

Un préréglage peut porter son **propre rapport d'aspect** (formats d'impression
comme *displate*). Les préréglages purement « résolution » (4K, 8K…) n'en
imposent aucun (carré par défaut) ; dans tous les cas un ``--ratio`` explicite
prime sur celui du préréglage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    """Préréglage de sortie : grand côté (px) et rapport d'aspect optionnel."""

    long_edge: int
    ratio: str | None = None  # None = pas de ratio imposé (carré par défaut)


# Préréglages standards d'affichage/impression. ``ratio=None`` = résolution seule
# (grand côté), le rapport d'aspect venant du ``--ratio`` ou du carré par défaut.
PRESETS: dict[str, Preset] = {
    "hd": Preset(1280),
    "fhd": Preset(1920),
    "1080p": Preset(1920),
    "2k": Preset(2560),
    "qhd": Preset(2560),
    "4k": Preset(3840),
    "uhd": Preset(3840),
    "8k": Preset(7680),
    "16k": Preset(15360),
    # Poster métal Displate : format portrait recommandé 4000x5600 (ratio 1:1.4).
    "displate": Preset(5600, "1:1.4"),
}


def parse_ratio(ratio: str) -> tuple[float, float]:
    """Analyse un rapport d'aspect ``"W:H"`` (ex. ``"16:9"``, ``"3:2"``, ``"1:1"``).

    Accepte aussi ``"W/H"`` et un simple nombre décimal (``"1.5"`` = ``3:2``).
    """
    s = str(ratio).strip().replace("/", ":")
    if ":" in s:
        a, b = s.split(":", 1)
        rw, rh = float(a), float(b)
    else:
        rw, rh = float(s), 1.0
    if rw <= 0 or rh <= 0:
        raise ValueError(f"Rapport d'aspect invalide : {ratio!r}")
    return rw, rh


def resolve_dimensions(
    preset: str | None = None,
    ratio: str | None = None,
    size: int | None = None,
) -> tuple[int, int]:
    """Calcule ``(width, height)`` en pixels.

    Le **grand côté** de sortie vaut ``preset`` s'il est fourni, sinon ``size``,
    sinon 1600 par défaut. Le rapport d'aspect façonne les deux dimensions autour
    de ce grand côté ; il est déterminé, par ordre de priorité :

    1. le ``ratio`` explicite passé ici (ex. ``"16:9"``) ;
    2. à défaut, le ratio propre au préréglage (ex. *displate* → ``"1:1.4"``) ;
    3. à défaut, ``"1:1"`` (carré) — ``size`` reproduit alors le comportement
       historique (image carrée).
    """
    preset_ratio = None
    if preset is not None:
        key = preset.strip().lower()
        if key not in PRESETS:
            raise ValueError(
                f"Préréglage inconnu : {preset!r} (attendus : {', '.join(sorted(PRESETS))})"
            )
        base = PRESETS[key].long_edge
        preset_ratio = PRESETS[key].ratio
    elif size is not None:
        base = int(size)
    else:
        base = 1600

    effective_ratio = ratio if ratio is not None else (preset_ratio or "1:1")
    rw, rh = parse_ratio(effective_ratio)
    if rw >= rh:
        width = base
        height = max(1, round(base * rh / rw))
    else:
        height = base
        width = max(1, round(base * rw / rh))
    return int(width), int(height)
