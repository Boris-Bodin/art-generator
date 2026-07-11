"""Viabilité : la dimension de box-counting rejette les formes quasi-1D."""

from __future__ import annotations

import numpy as np

from art_generator.core.rng import RNG
from art_generator.generators import quality


def _cloud(n, seed):
    return np.random.default_rng(seed).random((n, 2))


def test_box_dimension_separates_2d_from_degenerate():
    # Remplissage surfacique : dimension proche de 2.
    filled = _cloud(20000, 0)
    assert quality.box_dimension(filled) > 1.6

    # Effondrement en un point fixe (attracteur dégénéré) : dimension nulle.
    collapsed = np.zeros((20000, 2))
    assert quality.box_dimension(collapsed) < quality._MIN_DIMENSION

    # Courbe fine diagonale : ~1D, sous le remplissage surfacique.
    t = np.linspace(0, 1, 20000)
    line = np.column_stack((t, t))
    assert quality.box_dimension(line) < 1.3


def test_thin_curve_with_high_occupancy_is_rejected():
    # Un cercle fin occupe beaucoup de cellules (occupation OK) mais reste 1D.
    theta = np.linspace(0, 2 * np.pi, 8000)
    ring = np.column_stack((np.cos(theta), np.sin(theta)))
    assert quality.occupancy(ring) >= quality._MIN_CELLS
    assert quality.box_dimension(ring) < 1.3  # bien en dessous d'un remplissage 2D


def test_viable_params_satisfy_dimension_floor():
    # Les paramètres retenus par le générateur ne sont jamais quasi-1D.
    for family in ("attractor", "polar", "complex"):
        for s in range(5):
            params = quality.viable_params(family, RNG(s))
            eq = quality.registry.build(family, params)
            pts, _ = eq.sample(6000)
            if quality.occupancy(pts) >= quality._MIN_CELLS:
                assert quality.box_dimension(pts) >= quality._MIN_DIMENSION


def test_viable_params_is_deterministic():
    a = quality.viable_params("attractor", RNG(3))
    b = quality.viable_params("attractor", RNG(3))
    assert a == b
