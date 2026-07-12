"""Dimension temporelle : dérive un génome statique à un instant ``t``.

L'animation vit **au-dessus** du moteur, sous forme d'une fonction pure ::

    frame(t) = Engine.render(evaluate(genome, t))          pour t dans [0, 1]

:func:`evaluate` copie le génome, puis pour chaque :class:`Track` interpole la
valeur de l'image-clé à l'instant ``t`` et l'écrit à l'adresse ``target``. Le
moteur, le registre et le renderer ignorent tout du temps : monter en résolution,
tiling, indépendance à la résolution — tout est hérité tel quel.

Invariant : ``genome.animation is None`` ⇒ :func:`evaluate` est l'identité ⇒
rendu **identique au pixel près** à l'œuvre statique. Aucune régression possible.

L'interpolation n'emploie **aucun aléa** : elle est trivialement reproductible.
La ``seed`` et les ``equation_params['seed']`` restent fixes sur toutes les
images, donc la structure ne « saute » pas d'une frame à l'autre ; seuls les
champs ciblés par une piste évoluent.
"""

from __future__ import annotations

import copy
from dataclasses import is_dataclass
from typing import Any

import numpy as np

from .genome import AnimationGenome, ArtworkGenome, Keyframe, Track

# Keyframes échantillonnant la rotation d'un dégradé (couleurs le long des arrêts).
_GRADIENT_CYCLE_STEPS = 12

# --- résolution de chemin dans le génome ------------------------------------
#
# Un ``target`` de piste est un chemin pointé qui traverse indifféremment des
# dataclasses (attributs), des dicts (clés), des listes et des tuples (index
# entiers). Exemples :
#
#     "layers.0.symmetry_order"          -> genome.layers[0].symmetry_order
#     "layers.0.equation_params.a"       -> genome.layers[0].equation_params["a"]
#     "background_params.angle"          -> genome.background_params["angle"]
#     "layers.0.palette.phase.1"         -> genome.layers[0].palette.phase[1]


def _segments(target: str) -> list[Any]:
    """Découpe ``"layers.0.palette.phase.1"`` en ``["layers", 0, "palette", ...]``.

    Un segment purement numérique devient un index entier (liste/tuple).
    """
    parts: list[Any] = []
    for part in target.split("."):
        parts.append(int(part) if part.lstrip("-").isdigit() else part)
    return parts


def _child(node: Any, key: Any) -> Any:
    """Descend d'un cran dans ``node`` selon le type du conteneur."""
    if is_dataclass(node):
        return getattr(node, key)
    if isinstance(node, dict):
        return node[key]
    return node[key]  # list / tuple : index entier


def get_path(root: Any, target: str) -> Any:
    """Lit la valeur adressée par le chemin ``target`` dans ``root``."""
    node = root
    for key in _segments(target):
        node = _child(node, key)
    return node


def set_path(root: Any, target: str, value: Any) -> None:
    """Écrit ``value`` à l'adresse ``target`` dans ``root`` (mutation en place).

    Les tuples étant immuables (ex. ``palette.phase``), on les reconstruit et on
    les réinjecte récursivement dans leur conteneur parent.
    """
    _set_segments(root, _segments(target), value)


def _set_segments(node: Any, segs: list[Any], value: Any) -> None:
    key = segs[0]
    if len(segs) == 1:
        if is_dataclass(node):
            setattr(node, key, value)
        elif isinstance(node, dict):
            node[key] = value
        elif isinstance(node, tuple):
            # Impossible : géré par le cas tuple ci-dessous (parent le remplace).
            raise TypeError("un tuple ne peut être muté ; passer par son parent")
        else:  # list
            node[key] = value
        return

    child = _child(node, key)
    if isinstance(child, tuple):
        # Reconstruit le tuple avec l'élément modifié, puis le réinjecte.
        items = list(child)
        _set_segments(items, segs[1:], value)
        _set_segments(node, [key], tuple(items))
    else:
        _set_segments(child, segs[1:], value)


# --- interpolation ----------------------------------------------------------


def _smoothstep(u: float) -> float:
    return u * u * (3.0 - 2.0 * u)


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _blend(a: Any, b: Any, u: float) -> Any:
    """Interpole entre deux valeurs, récursivement pour les listes imbriquées.

    Gère scalaires, vecteurs (ex. ``phase``) et listes de listes (ex. arrêts d'un
    dégradé ``[[pos, r, g, b], …]``).
    """
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return [_blend(x, y, u) for x, y in zip(a, b)]
    return _lerp(float(a), float(b), u)


def track_value(track: Track, t: float) -> Any:
    """Valeur interpolée d'une piste à l'instant ``t`` (bornée aux images-clés)."""
    kfs = sorted(track.keyframes, key=lambda k: k.t)
    if not kfs:
        raise ValueError(f"piste sans image-clé : {track.target!r}")
    if t <= kfs[0].t:
        return kfs[0].value
    if t >= kfs[-1].t:
        return kfs[-1].value

    for a, b in zip(kfs, kfs[1:]):
        if a.t <= t <= b.t:
            span = b.t - a.t
            u = 0.0 if span <= 0 else (t - a.t) / span
            if track.interp == "step":
                return a.value
            if track.interp == "smooth":
                u = _smoothstep(u)
            return _blend(a.value, b.value, u)
    return kfs[-1].value  # inatteignable (t est encadré)


def _coerce_like(template: Any, value: Any) -> Any:
    """Recale ``value`` sur le **type courant** du champ (``template``).

    Un champ entier (ex. ``symmetry_order``) reste entier après interpolation ;
    les vecteurs (tuple/list) sont recalés élément par élément et rendus dans le
    conteneur d'origine (tuple préservé).
    """
    if isinstance(template, bool):
        return bool(round(float(value)))
    if isinstance(template, int):
        return int(round(float(value)))
    if isinstance(template, (list, tuple)):
        recased = [_coerce_like(t, v) for t, v in zip(template, value)]
        return type(template)(recased)
    return float(value)


def evaluate(genome: ArtworkGenome, t: float) -> ArtworkGenome:
    """Dérive le génome statique de ``genome`` à l'instant ``t`` (``t`` dans [0, 1]).

    ``genome.animation is None`` ⇒ renvoie une copie inchangée (identité au pixel
    près). Sinon, applique chaque piste au champ ciblé, en préservant le type
    courant du champ.
    """
    result = copy.deepcopy(genome)
    result.animation = None
    if genome.animation is None:
        return result

    for track in genome.animation.tracks:
        raw = track_value(track, t)
        try:
            current = get_path(result, track.target)
        except (KeyError, IndexError, AttributeError):
            # Cible absente (ex. clé de background_params non présente pour ce
            # fond) : on écrit la valeur brute, sans recalage de type.
            current = None
        value = raw if current is None else _coerce_like(current, raw)
        set_path(result, track.target, value)
    return result


# --- horloge ----------------------------------------------------------------


def _gradient_cycle_track(index: int, palette) -> Track:
    """Piste faisant **tourner les couleurs** d'un dégradé le long de ses arrêts.

    Le mode ``gradient`` ignore ``phase`` : on garde les positions des arrêts et on
    y fait défiler les couleurs (dégradé traité cycliquement). Un tour complet
    revient au départ ⇒ boucle sans couture. Positions fixes d'une keyframe à
    l'autre (seules les couleurs changent) : interpolation linéaire valide.
    """
    stops = [list(s) for s in palette.stops]
    order = np.argsort([s[0] for s in stops])
    ppos = np.array([stops[o][0] for o in order], dtype=np.float64)
    pcol = np.array([stops[o][1:] for o in order], dtype=np.float64)  # (S, 3)
    ext_pos = np.concatenate(([ppos[-1] - 1.0], ppos, [ppos[0] + 1.0]))  # échantillonnage cyclique
    ext_col = np.concatenate((pcol[-1:], pcol, pcol[:1]), axis=0)
    orig = np.array([s[0] for s in stops], dtype=np.float64)

    def sample(query: np.ndarray) -> np.ndarray:
        q = query % 1.0
        return np.stack([np.interp(q, ext_pos, ext_col[:, c]) for c in range(3)], axis=-1)

    keyframes = []
    for j in range(_GRADIENT_CYCLE_STEPS + 1):
        p = j / _GRADIENT_CYCLE_STEPS
        cols = sample(orig - p)
        keyframes.append(Keyframe(p, [
            [float(orig[k]), float(cols[k, 0]), float(cols[k, 1]), float(cols[k, 2])]
            for k in range(len(stops))
        ]))
    return Track(f"layers.{index}.palette.stops", keyframes)


def color_cycle_track(index: int, layer) -> Track:
    """Piste de cyclage couleur d'une couche, **adaptée à son mode de palette**.

    hsv/hsl → teinte parcourue ; cosine → phase ; gradient → rotation des couleurs
    des arrêts (:func:`_gradient_cycle_track`). Rend le cyclage visible quel que
    soit le mode (le gradient, très courant, ignorerait ``phase``).
    """
    palette = layer.palette
    if palette.mode in ("hsv", "hsl"):
        h0 = float(palette.hue[0])
        return Track(f"layers.{index}.palette.hue.0", [Keyframe(0.0, h0), Keyframe(1.0, h0 + 1.0)])
    if palette.mode == "gradient" and palette.stops:
        return _gradient_cycle_track(index, palette)
    phase = list(palette.phase)  # cosine
    return Track(
        f"layers.{index}.palette.phase",
        [Keyframe(0.0, phase), Keyframe(1.0, [p + 1.0 for p in phase])],
    )


def frame_time(animation: AnimationGenome, index: int) -> float:
    """Instant ``t`` dans ``[0, 1]`` de la frame ``index``.

    En boucle, ``t = index / frames`` : la dernière frame précède le retour au
    début (pas de doublon à la couture). Sinon ``t = index / (frames - 1)`` pour
    atteindre exactement ``t = 1`` à la dernière frame.
    """
    n = max(1, animation.frames)
    if animation.loop:
        return (index % n) / n
    if n == 1:
        return 0.0
    return index / (n - 1)
