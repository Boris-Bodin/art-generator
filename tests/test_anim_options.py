"""Tests de la logique d'options d'animation de l'UI (sans toolkit)."""

from __future__ import annotations

import numpy as np

import art_generator as ag
from art_generator.core import animation as animation_core
from art_generator.core.engine import Engine
from art_generator.exporters import animation as anim_export
from art_generator.ui import anim_options
from art_generator.ui.anim_options import AnimationOptions


def test_no_effect_gives_no_animation():
    genome = ag.generate(42, 96, 96)
    opts = AnimationOptions(
        color_cycle=False, background_spin=False, particle_reveal=False, noise_flow=False
    )
    out = anim_options.apply(genome, opts)
    assert out.animation is None


def test_defaults_animate_background_and_color():
    genome = ag.generate(42, 96, 96)
    out = anim_options.apply(genome, AnimationOptions())
    assert out.animation is not None
    targets = {t.target for t in out.animation.tracks}
    assert "background_params.angle" in targets
    # une piste couleur par couche
    assert sum(t.target.endswith(("palette.hue.0",)) or "palette.phase" in t.target
               for t in out.animation.tracks) == len(genome.layers)


def test_input_genome_not_mutated():
    genome = ag.generate(42, 96, 96)
    before = genome_snapshot(genome)
    anim_options.apply(genome, AnimationOptions(particle_reveal=True, noise_flow=True))
    assert genome_snapshot(genome) == before
    assert genome.animation is None


def genome_snapshot(g):
    from art_generator.exporters import genome_io
    import json
    return json.dumps(genome_io.to_dict(g), sort_keys=True)


def test_particle_reveal_sets_param_and_track():
    genome = ag.generate(42, 96, 96)
    # seed 42 : couche 0 = particles
    assert genome.layers[0].equation_family == "particles"
    out = anim_options.apply(genome, AnimationOptions(particle_reveal=True))
    assert out.layers[0].equation_params.get("reveal") == 0.0
    assert "layers.0.equation_params.reveal" in {t.target for t in out.animation.tracks}


def test_noise_flow_enables_3d_and_track():
    genome = ag.generate(42, 96, 96)
    # seed 42 : couche 0 utilise un bruit simplex
    assert genome.layers[0].noise_type != "none"
    out = anim_options.apply(genome, AnimationOptions(noise_flow=True, color_cycle=False,
                                                      background_spin=False))
    assert out.layers[0].noise_3d is True
    assert "layers.0.noise_z" in {t.target for t in out.animation.tracks}


def test_result_renders_frames():
    genome = ag.generate(42, 96, 96)
    out = anim_options.apply(genome, AnimationOptions(frames=4))
    a = np.asarray(Engine().render(animation_core.evaluate(out, 0.0)))
    b = np.asarray(Engine().render(animation_core.evaluate(out, 0.5)))
    assert a.shape == (96, 96, 3)
    assert not np.array_equal(a, b)  # les frames diffèrent


def test_iter_frames_progress_callback():
    genome = ag.generate(42, 64, 64)
    out = anim_options.apply(genome, AnimationOptions(frames=3))
    calls = []
    list(anim_export.iter_frames(out, jobs=1, progress=lambda d, t: calls.append((d, t))))
    assert calls == [(1, 3), (2, 3), (3, 3)]
