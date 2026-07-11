"""Tests du bruit 3D temporel (Chantier B)."""

from __future__ import annotations

import numpy as np
import pytest

import art_generator as ag
from art_generator.core.engine import Engine
from art_generator.noise import fields


_KINDS = ("perlin", "simplex", "fbm", "worley")


@pytest.fixture
def grid():
    xs = np.linspace(-3.0, 3.0, 40)
    x, y = np.meshgrid(xs, xs)
    return x.ravel(), y.ravel()


@pytest.mark.parametrize("kind", _KINDS)
def test_sample3d_deterministic(kind, grid):
    x, y = grid
    z = np.full_like(x, 0.7)
    a = fields.sample3d(kind, x, y, z, 123)
    b = fields.sample3d(kind, x, y, z, 123)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("kind", _KINDS)
def test_sample3d_bounded_and_finite(kind, grid):
    x, y = grid
    z = np.full_like(x, 1.3)
    v = fields.sample3d(kind, x, y, z, 7)
    assert np.all(np.isfinite(v))
    assert np.abs(v).max() <= 1.2  # ~[-1, 1] avec petite marge


@pytest.mark.parametrize("kind", _KINDS)
def test_sample3d_varies_with_z(kind, grid):
    x, y = grid
    v0 = fields.sample3d(kind, x, y, np.zeros_like(x), 5)
    v1 = fields.sample3d(kind, x, y, np.full_like(x, 1.5), 5)
    assert not np.allclose(v0, v1)


@pytest.mark.parametrize("kind", ("perlin", "simplex", "fbm"))
def test_sample3d_continuous_in_z(kind, grid):
    """Un petit pas en z ⇒ petit changement (flux cohérent, pas de scintillement)."""
    x, y = grid
    v0 = fields.sample3d(kind, x, y, np.full_like(x, 0.50), 9)
    v1 = fields.sample3d(kind, x, y, np.full_like(x, 0.51), 9)
    assert np.max(np.abs(v1 - v0)) < 0.2


def test_noise_3d_disabled_is_pixel_identical():
    """``noise_3d=False`` (défaut) ⇒ rendu inchangé quel que soit ``noise_z``."""
    genome = ag.generate(321, 160, 160)
    layer = genome.layers[0]
    layer.noise_type = "simplex"
    layer.warp = 0.3
    layer.color_noise = 0.4
    base = np.asarray(Engine().render(genome))

    layer.noise_z = 5.0  # doit être ignoré quand noise_3d est faux
    same = np.asarray(Engine().render(genome))
    assert np.array_equal(base, same)


def test_noise_3d_enabled_changes_with_z():
    genome = ag.generate(321, 160, 160)
    layer = genome.layers[0]
    layer.noise_type = "simplex"
    layer.warp = 0.4
    layer.color_noise = 0.4
    layer.noise_3d = True

    layer.noise_z = 0.0
    a = np.asarray(Engine().render(genome))
    layer.noise_z = 2.0
    b = np.asarray(Engine().render(genome))
    assert not np.array_equal(a, b)
