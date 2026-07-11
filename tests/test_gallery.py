"""La génération de galerie en parallèle doit rester identique au séquentiel."""

from __future__ import annotations

import numpy as np

from art_generator.examples.generate_gallery import build_gallery


def test_parallel_gallery_is_pixel_identical_to_sequential():
    seeds = [1, 2, 3, 7]
    tile, cols = 64, 2
    sequential = build_gallery(seeds, tile, cols, jobs=1)
    parallel = build_gallery(seeds, tile, cols, jobs=2)
    assert parallel.size == (cols * tile, 2 * tile)
    assert np.array_equal(np.asarray(sequential), np.asarray(parallel))
