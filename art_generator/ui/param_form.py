"""Modèle d'un formulaire de paramètres d'équation — logique pure, sans toolkit.

L'éditeur de paramètres de l'UI ne manipule plus du JSON brut : il présente un
**champ typé par paramètre**. Ce module fournit la logique testable sous-jacente,
indépendante de Tkinter :

* :func:`describe` aplatit un dict de paramètres (éventuellement imbriqué) en une
  liste de :class:`Field`, en **inférant le type** de chaque valeur (booléen,
  entier, flottant, texte, énumération, ou JSON pour les structures) ;
* :func:`coerce` convertit la saisie d'un widget vers le type du champ ;
* :func:`assemble` reconstruit le dict imbriqué à partir des valeurs éditées, en
  préservant la structure et les clés non exposées.

Les énumérations connues (``variant`` selon la famille, type d'émetteur, etc.)
deviennent des listes de choix ; le reste s'infère de la valeur courante.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field as _field
from typing import Any

# Énumérations dépendant de la famille (même clé, valeurs différentes).
_CHOICES_BY_FAMILY: dict[tuple[str, str], tuple[str, ...]] = {
    ("attractor", "variant"): ("clifford", "dejong", "custom"),
    ("complex", "variant"): ("poly", "sinus", "rational"),
    ("fractal", "variant"): ("mandelbrot", "julia"),
}

# Énumérations indépendantes de la famille (clé suffisamment spécifique).
_CHOICES_BY_KEY: dict[str, tuple[str, ...]] = {
    "type": ("point", "disk", "ring", "line"),  # emitter.type
    "noise_type": ("none", "perlin", "simplex", "fbm", "worley"),
    "color_by": ("age", "speed"),
}


@dataclass(frozen=True)
class Field:
    """Un paramètre éditable : chemin dans le dict, type inféré, valeur, choix."""

    path: tuple[str, ...]
    kind: str  # "bool" | "int" | "float" | "str" | "choice" | "json"
    value: Any
    choices: tuple[str, ...] = _field(default_factory=tuple)

    @property
    def label(self) -> str:
        """Étiquette lisible : chemin pointé (ex. ``emitter.type``)."""
        return ".".join(self.path)


def _choices_for(family: str, path: tuple[str, ...]) -> tuple[str, ...]:
    key = path[-1]
    if (family, key) in _CHOICES_BY_FAMILY:
        return _CHOICES_BY_FAMILY[(family, key)]
    return _CHOICES_BY_KEY.get(key, ())


def describe(params: dict[str, Any], family: str = "") -> list[Field]:
    """Aplatit ``params`` en champs typés (récursif sur les dicts imbriqués)."""
    fields: list[Field] = []

    def walk(node: dict[str, Any], prefix: tuple[str, ...]) -> None:
        for key, value in node.items():
            path = (*prefix, key)
            if isinstance(value, bool):
                fields.append(Field(path, "bool", value))
            elif isinstance(value, int):
                fields.append(Field(path, "int", value))
            elif isinstance(value, float):
                fields.append(Field(path, "float", value))
            elif isinstance(value, str):
                choices = _choices_for(family, path)
                kind = "choice" if choices else "str"
                fields.append(Field(path, kind, value, choices))
            elif isinstance(value, dict):
                walk(value, path)
            else:  # list / tuple / None : édité en JSON
                fields.append(Field(path, "json", value))

    walk(params, ())
    return fields


def coerce(kind: str, raw: Any) -> Any:
    """Convertit une saisie de widget vers le type d'un champ.

    Lève ``ValueError`` (ou ``json.JSONDecodeError``) sur saisie invalide, à la
    charge de l'appelant de la présenter à l'utilisateur.
    """
    if kind == "bool":
        return bool(raw)
    if kind == "int":
        return int(str(raw).strip())
    if kind == "float":
        return float(str(raw).strip())
    if kind == "json":
        return json.loads(raw)
    return str(raw)


def assemble(base: dict[str, Any], updates: list[tuple[tuple[str, ...], Any]]) -> dict[str, Any]:
    """Reconstruit ``base`` en y injectant les valeurs éditées (chemins imbriqués).

    Les clés non listées dans ``updates`` sont conservées telles quelles.
    """
    result = copy.deepcopy(base)
    for path, value in updates:
        node = result
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return result
