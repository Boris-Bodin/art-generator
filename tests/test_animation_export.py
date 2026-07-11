"""Tests de l'export temporel (Chantier D) : GIF, séquence PNG, dispatch."""

from __future__ import annotations

from PIL import Image

import art_generator as ag
from art_generator.core.genome import AnimationGenome, Keyframe, Track
from art_generator.exporters import animation as anim_export


def _tiny_animated(seed: int = 3, frames: int = 4):
    genome = ag.generate(seed, 96, 96)
    genome.animation = AnimationGenome(
        fps=12,
        frames=frames,
        loop=True,
        tracks=[Track("layers.0.opacity", [Keyframe(0.0, 1.0), Keyframe(1.0, 0.3)])],
    )
    return genome


def test_iter_frames_count_and_size():
    genome = _tiny_animated(frames=5)
    frames = list(anim_export.iter_frames(genome, jobs=1))
    assert len(frames) == 5
    assert all(isinstance(f, Image.Image) and f.size == (96, 96) for f in frames)


def test_frames_change_over_time():
    import numpy as np

    genome = _tiny_animated()
    frames = list(anim_export.iter_frames(genome, jobs=1))
    # L'opacité varie : la première et la dernière frame diffèrent.
    assert not np.array_equal(np.asarray(frames[0]), np.asarray(frames[-1]))


def test_save_gif(tmp_path):
    genome = _tiny_animated(frames=4)
    out = anim_export.save_gif(genome, tmp_path / "a.gif", jobs=1)
    assert out.exists()
    with Image.open(out) as im:
        assert getattr(im, "n_frames", 1) == 4


def test_save_png_sequence(tmp_path):
    genome = _tiny_animated(frames=3)
    out = anim_export.save_png_sequence(genome, tmp_path / "seq", jobs=1)
    files = sorted(out.glob("frame_*.png"))
    assert [f.name for f in files] == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]


def test_save_animation_dispatch_gif(tmp_path):
    genome = _tiny_animated(frames=3)
    out = anim_export.save_animation(genome, tmp_path / "d.gif", jobs=1)
    assert out.suffix == ".gif" and out.exists()


def test_save_animation_dispatch_png_sequence(tmp_path):
    genome = _tiny_animated(frames=3)
    out = anim_export.save_animation(genome, tmp_path / "frames_dir", jobs=1)
    assert out.is_dir() and len(list(out.glob("*.png"))) == 3


def test_default_spin_animation_used_when_none():
    genome = ag.generate(7, 96, 96)
    assert genome.animation is None
    # À défaut d'animation, une « spin » par défaut est fabriquée (structure) :
    # rotation du fond + un cyclage couleur par couche.
    used = anim_export._ensure_animation(genome)
    assert used.frames == 90 and used.loop is True
    assert "background_params.angle" in {t.target for t in used.tracks}
    assert len(used.tracks) == 1 + len(genome.layers)


def test_default_spin_cycles_color_per_palette_mode():
    genome = ag.generate(7, 64, 64)
    genome.layers[0].palette.mode = "hsl"
    anim = anim_export.default_spin_animation(genome)
    targets = {t.target for t in anim.tracks}
    assert "layers.0.palette.hue.0" in targets  # hsl -> teinte

    genome.layers[0].palette.mode = "cosine"
    anim = anim_export.default_spin_animation(genome)
    targets = {t.target for t in anim.tracks}
    assert "layers.0.palette.phase" in targets  # cosinus -> phase


def test_default_spin_renders_on_arbitrary_genome():
    # Le spin par défaut cible background_params.angle même si la clé est absente :
    # evaluate doit rester robuste (pas de KeyError).
    genome = ag.generate(7, 64, 64)
    genome.animation = anim_export.default_spin_animation(genome, frames=2)
    frames = list(anim_export.iter_frames(genome, jobs=1))
    assert len(frames) == 2


def test_export_is_deterministic(tmp_path):
    import numpy as np

    genome = _tiny_animated(frames=3)
    a = list(anim_export.iter_frames(genome, jobs=1))
    b = list(anim_export.iter_frames(genome, jobs=1))
    for fa, fb in zip(a, b):
        assert np.array_equal(np.asarray(fa), np.asarray(fb))
