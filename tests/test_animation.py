"""Tests du modèle temporel (Chantier A) : évaluation, chemins, invariants."""

from __future__ import annotations

import numpy as np

import art_generator as ag
from art_generator.core import animation
from art_generator.core.engine import Engine
from art_generator.core.genome import AnimationGenome, Keyframe, Track
from art_generator.exporters import genome_io


def _pixels(genome):
    return np.asarray(Engine().render(genome))


# --- invariant : sans animation, rien ne change -----------------------------


def test_evaluate_without_animation_is_identity_pixels():
    genome = ag.generate(777, 256, 256)
    assert genome.animation is None
    derived = animation.evaluate(genome, 0.5)
    assert np.array_equal(_pixels(genome), _pixels(derived))


def test_evaluate_strips_animation_on_result():
    genome = ag.generate(1, 128, 128)
    genome.animation = AnimationGenome(
        tracks=[Track("layers.0.opacity", [Keyframe(0.0, 1.0), Keyframe(1.0, 0.2)])]
    )
    assert animation.evaluate(genome, 0.0).animation is None


# --- chemins pointés --------------------------------------------------------


def test_get_and_set_dataclass_dict_and_tuple_paths():
    genome = ag.generate(3, 128, 128)
    genome.background_params = {"angle": 0.0}

    animation.set_path(genome, "layers.0.symmetry_order", 8)
    assert genome.layers[0].symmetry_order == 8

    animation.set_path(genome, "background_params.angle", 1.25)
    assert genome.background_params["angle"] == 1.25

    # tuple immuable (phase de palette) reconstruit puis réinjecté
    animation.set_path(genome, "layers.0.palette.phase.1", 0.9)
    assert genome.layers[0].palette.phase[1] == 0.9
    assert isinstance(genome.layers[0].palette.phase, tuple)
    assert animation.get_path(genome, "layers.0.palette.phase.1") == 0.9


# --- interpolation ----------------------------------------------------------


def test_track_value_hits_keyframes_exactly():
    track = Track("x", [Keyframe(0.0, 10.0), Keyframe(1.0, 20.0)])
    assert animation.track_value(track, 0.0) == 10.0
    assert animation.track_value(track, 1.0) == 20.0
    assert animation.track_value(track, 0.5) == 15.0  # linéaire


def test_track_value_clamps_outside_range():
    track = Track("x", [Keyframe(0.2, 5.0), Keyframe(0.8, 9.0)])
    assert animation.track_value(track, 0.0) == 5.0
    assert animation.track_value(track, 1.0) == 9.0


def test_interp_modes():
    kfs = [Keyframe(0.0, 0.0), Keyframe(1.0, 10.0)]
    assert animation.track_value(Track("x", kfs, "step"), 0.5) == 0.0
    assert animation.track_value(Track("x", kfs, "smooth"), 0.5) == 5.0  # smoothstep(0.5)=0.5
    assert animation.track_value(Track("x", kfs, "linear"), 0.25) == 2.5


def test_vector_keyframes_interpolate_elementwise():
    track = Track("p", [Keyframe(0.0, [0.0, 0.0]), Keyframe(1.0, [1.0, 3.0])])
    assert animation.track_value(track, 0.5) == [0.5, 1.5]


# --- recalage de type -------------------------------------------------------


def test_evaluate_preserves_int_field_type():
    genome = ag.generate(5, 128, 128)
    genome.layers[0].symmetry_order = 4
    genome.animation = AnimationGenome(
        tracks=[Track("layers.0.symmetry_order", [Keyframe(0.0, 4), Keyframe(1.0, 9)])]
    )
    order = animation.evaluate(genome, 0.5).layers[0].symmetry_order
    assert order == 6 and isinstance(order, int)


def test_evaluate_preserves_tuple_field():
    genome = ag.generate(6, 128, 128)
    genome.layers[0].palette.phase = (0.0, 0.0, 0.0)
    genome.animation = AnimationGenome(
        tracks=[Track("layers.0.palette.phase", [Keyframe(0.0, [0.0, 0.0, 0.0]),
                                                 Keyframe(1.0, [1.0, 1.0, 1.0])])]
    )
    phase = animation.evaluate(genome, 0.5).layers[0].palette.phase
    assert isinstance(phase, tuple)
    assert phase == (0.5, 0.5, 0.5)


# --- horloge ----------------------------------------------------------------


def test_frame_time_loop_excludes_endpoint():
    anim = AnimationGenome(frames=4, loop=True)
    assert [animation.frame_time(anim, i) for i in range(4)] == [0.0, 0.25, 0.5, 0.75]


def test_frame_time_non_loop_reaches_one():
    anim = AnimationGenome(frames=5, loop=False)
    assert animation.frame_time(anim, 0) == 0.0
    assert animation.frame_time(anim, 4) == 1.0


# --- sérialisation ----------------------------------------------------------


def test_animation_json_round_trip(tmp_path):
    genome = ag.generate(42, 128, 128)
    genome.animation = AnimationGenome(
        fps=24,
        frames=48,
        loop=False,
        tracks=[
            Track("layers.0.opacity", [Keyframe(0.0, 1.0), Keyframe(1.0, 0.3)], "smooth"),
            Track("background_params.angle", [Keyframe(0.0, 0.0), Keyframe(1.0, 6.28)]),
        ],
    )
    path = genome_io.save(genome, tmp_path / "anim.json")
    reloaded = genome_io.load(path)

    assert reloaded.animation is not None
    assert reloaded.animation.fps == 24
    assert reloaded.animation.frames == 48
    assert reloaded.animation.loop is False
    assert len(reloaded.animation.tracks) == 2
    assert reloaded.animation.tracks[0].interp == "smooth"
    # évaluation identique après round-trip
    assert np.array_equal(_pixels(animation.evaluate(genome, 0.5)),
                          _pixels(animation.evaluate(reloaded, 0.5)))


def test_legacy_json_without_animation_loads(tmp_path):
    genome = ag.generate(11, 128, 128)
    data = genome_io.to_dict(genome)
    data.pop("animation", None)  # simule un génome antérieur à la V2
    import json

    p = tmp_path / "legacy.json"
    p.write_text(json.dumps(data), "utf-8")
    reloaded = genome_io.load(p)
    assert reloaded.animation is None


# --- déterminisme temporel --------------------------------------------------


def test_frames_are_deterministic():
    genome = ag.generate(99, 128, 128)
    genome.animation = AnimationGenome(
        frames=6,
        tracks=[Track("layers.0.opacity", [Keyframe(0.0, 1.0), Keyframe(1.0, 0.2)])],
    )
    a = _pixels(animation.evaluate(genome, 0.4))
    b = _pixels(animation.evaluate(genome, 0.4))
    assert np.array_equal(a, b)
