"""Registre des familles d'équations.

Point d'extension unique du moteur : ajouter une famille = enregistrer une
classe :class:`~art_generator.equations.base.Equation` et son générateur de
paramètres par défaut. Rien d'autre dans le code n'a besoin de la connaître.
"""

from __future__ import annotations

from typing import Any, Callable

from . import attractors, complex_map, fractal, parametric, polar, vector_field
from .base import Equation

# famille -> (classe d'équation, fabrique de paramètres depuis un RNG)
_REGISTRY: dict[str, tuple[type[Equation], Callable[[Any], dict]]] = {}


def register(
    family: str,
    equation_cls: type[Equation],
    param_factory: Callable[[Any], dict],
) -> None:
    _REGISTRY[family] = (equation_cls, param_factory)


def families() -> list[str]:
    """Liste triée des familles disponibles."""
    return sorted(_REGISTRY)


def build(family: str, params: dict[str, Any]) -> Equation:
    """Instancie l'équation d'une famille avec des paramètres donnés."""
    if family not in _REGISTRY:
        raise KeyError(f"Famille d'équation inconnue : {family!r}")
    return _REGISTRY[family][0](params)


def random_params(family: str, rng) -> dict[str, Any]:
    """Génère des paramètres par défaut harmonieux pour une famille."""
    return _REGISTRY[family][1](rng)


# --- enregistrement des familles fournies ---------------------------------
register("parametric", parametric.ParametricCurve, parametric.default_params)
register("polar", polar.PolarCurve, polar.default_params)
register("attractor", attractors.Attractor, attractors.default_params)
register("vector_field", vector_field.VectorField, vector_field.default_params)
register("complex", complex_map.ComplexMap, complex_map.default_params)
register("fractal", fractal.Fractal, fractal.default_params)
