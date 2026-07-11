"""Tests des particules temporelles (Chantier C) : fenêtre ``reveal``."""

from __future__ import annotations

import numpy as np

from art_generator.equations.particles import ParticleSystem, default_params
from art_generator.core.rng import RNG


def _params(**over):
    p = default_params(RNG(4))
    p.update(over)
    return p


def test_reveal_none_is_full_trajectory():
    """``reveal`` absent ⇒ comportement historique, points identiques."""
    p = _params()
    p.pop("reveal", None)
    a = ParticleSystem(dict(p)).sample(40_000)
    b = ParticleSystem(dict(p)).sample(40_000)
    assert np.array_equal(a[0], b[0])  # déterminisme conservé
    # Une fenêtre pleine (reveal fabriqué à 1.0 large) émet moins que le tout.
    full = a[0]
    windowed = ParticleSystem({**p, "reveal": 1.0, "trail": 0.2}).sample(40_000)[0]
    assert len(windowed) < len(full)


def test_reveal_window_constant_point_count():
    """La fenêtre a une largeur constante ⇒ même nombre de points à tout t."""
    p = _params(trail=0.2)
    counts = {
        r: len(ParticleSystem({**p, "reveal": r}).sample(40_000)[0])
        for r in (0.0, 0.3, 0.6, 1.0)
    }
    assert len(set(counts.values())) == 1  # identique pour tous les reveal


def test_reveal_advances_positions():
    """La fenêtre glisse : début et fin de l'animation diffèrent."""
    p = _params(trail=0.15)
    start = ParticleSystem({**p, "reveal": 0.0}).sample(40_000)[0]
    end = ParticleSystem({**p, "reveal": 1.0}).sample(40_000)[0]
    assert not np.array_equal(start, end)


def test_reveal_output_smaller_than_full():
    p = _params(trail=0.1)
    full = ParticleSystem({**{k: v for k, v in p.items() if k != "reveal"}}).sample(60_000)[0]
    win = ParticleSystem({**p, "reveal": 0.5}).sample(60_000)[0]
    assert len(win) < len(full)
