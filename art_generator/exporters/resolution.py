"""Résolutions de sortie : préréglages, rapport d'aspect, dimensions (Phase 5).

Le génome ne connaît que ``width``/``height`` en pixels. Ce module traduit des
intentions de haut niveau (« 4K en 16:9 ») en un couple ``(width, height)`` que
l'on injecte dans le génome avant rendu. Le grand côté du préréglage est assigné
à la plus grande dimension du rapport d'aspect ; l'orientation suit le rapport.
"""

from __future__ import annotations

# Grand côté (px) de chaque préréglage — l'un des standards d'affichage/impression.
PRESETS: dict[str, int] = {
    "hd": 1280,
    "fhd": 1920,
    "1080p": 1920,
    "2k": 2560,
    "qhd": 2560,
    "4k": 3840,
    "uhd": 3840,
    "8k": 7680,
    "16k": 15360,
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
    ratio: str = "1:1",
    size: int | None = None,
) -> tuple[int, int]:
    """Calcule ``(width, height)`` en pixels.

    Le **grand côté** de sortie vaut ``preset`` s'il est fourni, sinon ``size``,
    sinon 1600 par défaut. Le rapport d'aspect ``ratio`` façonne les deux
    dimensions autour de ce grand côté ; avec le ``ratio`` carré par défaut,
    ``size`` reproduit donc le comportement historique (image carrée).
    """
    if preset is not None:
        key = preset.strip().lower()
        if key not in PRESETS:
            raise ValueError(
                f"Préréglage inconnu : {preset!r} (attendus : {', '.join(sorted(PRESETS))})"
            )
        base = PRESETS[key]
    elif size is not None:
        base = int(size)
    else:
        base = 1600

    rw, rh = parse_ratio(ratio)
    if rw >= rh:
        width = base
        height = max(1, round(base * rh / rw))
    else:
        height = base
        width = max(1, round(base * rw / rh))
    return int(width), int(height)
