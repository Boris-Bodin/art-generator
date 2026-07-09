"""Système de particules : émetteurs, forces, turbulence.

Un ensemble de particules est simulé pas à pas :
chaque particule possède **position, vitesse, durée de vie, âge**. À chaque pas
on lui applique des **forces** (gravité, attraction/répulsion centrale, tourbillon,
traînée) et une **turbulence** issue d'un champ de bruit *curl* (sans divergence,
donc naturellement fluide). Les particules mortes **renaissent** à l'émetteur, ce
qui entretient un flux continu.

Le système reste dans le modèle unifié « nuage de points » : on **enregistre la
position de chaque particule à chaque pas**, ce qui donne ``steps × n_particles``
points. La coloration se fait par âge (le long de la trajectoire) ou par vitesse.
C'est le même dénominateur commun que toutes les autres familles, donc ni le
moteur ni le renderer n'ont à connaître les particules.

Passage à l'échelle : le nombre de points demandé ``n`` pilote le nombre de pas
(``steps = n // n_particles``) ; on atteint aisément le million de points en
gardant quelques milliers de particules simultanées.

Comme les autres équations, ce module n'a **pas** accès au RNG global : tout
l'aléa (positions initiales, renaissances) dérive de ``params['seed']`` via un
``numpy.random.default_rng`` local, ce qui garantit la reproductibilité au pixel
près et le round-trip JSON.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..noise import fields as noise
from .base import Equation

_EMITTERS = ("point", "disk", "ring", "line")


def _spawn(
    gen: np.random.Generator, count: int, emitter: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    """Positions et vitesses initiales de ``count`` particules pour un émetteur.

    Retourne ``(pos[count, 2], vel[count, 2])``. La forme de l'émetteur fixe la
    distribution des positions ; la vitesse est radiale (vers l'extérieur) avec
    une composante tangentielle (``swirl``) et une dispersion gaussienne.
    """
    if count <= 0:
        return np.empty((0, 2)), np.empty((0, 2))

    etype = emitter.get("type", "disk")
    cx = float(emitter.get("cx", 0.0))
    cy = float(emitter.get("cy", 0.0))
    radius = float(emitter.get("radius", 0.6))

    if etype == "point":
        pos = np.column_stack(
            (np.full(count, cx), np.full(count, cy))
        ).astype(np.float64)
    elif etype == "ring":
        theta = gen.uniform(0.0, 2.0 * np.pi, count)
        pos = np.column_stack((cx + radius * np.cos(theta), cy + radius * np.sin(theta)))
    elif etype == "line":
        angle = float(emitter.get("angle", 0.0))
        length = float(emitter.get("length", 2.0))
        t = gen.uniform(-0.5, 0.5, count) * length
        pos = np.column_stack((cx + t * np.cos(angle), cy + t * np.sin(angle)))
    else:  # "disk" (défaut) : disque uniforme
        theta = gen.uniform(0.0, 2.0 * np.pi, count)
        rr = radius * np.sqrt(gen.uniform(0.0, 1.0, count))
        pos = np.column_stack((cx + rr * np.cos(theta), cy + rr * np.sin(theta)))

    # Vitesse initiale : radiale depuis le centre + tangentielle + dispersion.
    speed = float(emitter.get("speed", 0.0))
    spread = float(emitter.get("spread", 0.3))
    swirl = float(emitter.get("swirl", 0.0))
    d = pos - np.array([cx, cy])
    norm = np.hypot(d[:, 0], d[:, 1])
    safe = np.maximum(norm, 1e-9)
    radial = d / safe[:, None]
    tangent = np.column_stack((-radial[:, 1], radial[:, 0]))
    vel = speed * radial + swirl * tangent
    vel = vel + spread * gen.standard_normal((count, 2))
    return pos, vel


class ParticleSystem(Equation):
    """Ensemble de particules simulées sous l'action de forces et d'une turbulence."""

    family = "particles"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        n_particles = int(p.get("n_particles", 3000))
        # On borne pour garantir au moins quelques pas même quand ``n`` est petit
        # (sondage de viabilité) et pour ne pas exploser la mémoire.
        n_particles = max(1, min(n_particles, max(1, n // 4)))
        steps = max(4, n // n_particles)
        dt = float(p.get("dt", 0.03))

        emitter = dict(p.get("emitter", {}))
        forces = dict(p.get("forces", {}))
        turb = dict(p.get("turbulence", {}))

        gx = float(forces.get("gravity_x", 0.0))
        gy = float(forces.get("gravity_y", 0.0))
        drag = float(forces.get("drag", 0.1))
        central = float(forces.get("central", 0.0))
        vortex = float(forces.get("vortex", 0.0))

        t_amp = float(turb.get("amp", 0.0))
        t_freq = float(turb.get("freq", 1.2))
        t_kind = str(turb.get("noise_type", "simplex"))
        t_seed = int(turb.get("seed", 12345))

        life_mean = float(p.get("life", max(6.0, steps * 0.6)))
        color_by = str(p.get("color_by", "age"))

        gen = np.random.default_rng(int(p["seed"]))
        pos, vel = _spawn(gen, n_particles, emitter)
        life = gen.uniform(0.5 * life_mean, 1.5 * life_mean, n_particles)
        age = np.zeros(n_particles, dtype=np.float64)

        xs = np.empty((steps, n_particles), dtype=np.float64)
        ys = np.empty((steps, n_particles), dtype=np.float64)
        cval = np.empty((steps, n_particles), dtype=np.float64)

        eps = 0.5 / max(t_freq, 1e-6)  # pas des différences finies pour le curl
        for s in range(steps):
            ax = np.full(n_particles, gx)
            ay = np.full(n_particles, gy)

            if central != 0.0:
                # Ressort linéaire vers l'origine (central > 0 attire, < 0 repousse).
                ax = ax - central * pos[:, 0]
                ay = ay - central * pos[:, 1]

            if vortex != 0.0:
                # Champ rotationnel autour de l'origine : perpendiculaire au rayon.
                ax = ax - vortex * pos[:, 1]
                ay = ay + vortex * pos[:, 0]

            if t_amp > 0.0:
                # Bruit *curl* : v = (∂ψ/∂y, -∂ψ/∂x) — sans divergence, donc fluide.
                x, y = pos[:, 0], pos[:, 1]

                def psi(px: np.ndarray, py: np.ndarray) -> np.ndarray:
                    return noise.sample(t_kind, px * t_freq, py * t_freq, t_seed)

                dpx = (psi(x + eps, y) - psi(x - eps, y)) / (2.0 * eps)
                dpy = (psi(x, y + eps) - psi(x, y - eps)) / (2.0 * eps)
                ax = ax + t_amp * dpy
                ay = ay - t_amp * dpx

            # Traînée (amortissement visqueux) puis intégration d'Euler.
            vel[:, 0] += (ax - drag * vel[:, 0]) * dt
            vel[:, 1] += (ay - drag * vel[:, 1]) * dt
            pos[:, 0] += vel[:, 0] * dt
            pos[:, 1] += vel[:, 1] * dt

            xs[s] = pos[:, 0]
            ys[s] = pos[:, 1]
            if color_by == "speed":
                cval[s] = np.hypot(vel[:, 0], vel[:, 1])
            else:  # "age" : fraction de vie écoulée le long de la trajectoire
                cval[s] = np.clip(age / np.maximum(life, 1e-9), 0.0, 1.0)

            # Vieillissement et renaissance des particules mortes à l'émetteur.
            age += 1.0
            dead = age >= life
            k = int(dead.sum())
            if k:
                npos, nvel = _spawn(gen, k, emitter)
                pos[dead] = npos
                vel[dead] = nvel
                life[dead] = gen.uniform(0.5 * life_mean, 1.5 * life_mean, k)
                age[dead] = 0.0

        points = np.column_stack((xs.ravel(order="F"), ys.ravel(order="F")))
        values = cval.ravel(order="F")

        if color_by == "speed":
            finite = np.isfinite(values)
            if finite.any():
                lo, hi = np.percentile(values[finite], (2.0, 98.0))
                if hi - lo > 1e-12:
                    values = np.clip((values - lo) / (hi - lo), 0.0, 1.0)
                else:
                    values = np.zeros_like(values)
        return points, values


def default_params(rng) -> dict[str, Any]:
    """Tire un système de particules varié mais plausible depuis un ``RNG``."""
    emitter_type = rng.choice(list(_EMITTERS), weights=[0.15, 0.4, 0.3, 0.15])
    emitter = {
        "type": emitter_type,
        "cx": rng.uniform(-0.4, 0.4),
        "cy": rng.uniform(-0.4, 0.4),
        "radius": rng.uniform(0.3, 1.0),
        "angle": rng.uniform(0.0, 3.14159),
        "length": rng.uniform(1.2, 2.6),
        "speed": rng.uniform(0.0, 0.8),
        "spread": rng.uniform(0.15, 0.6),
        "swirl": rng.uniform(-0.8, 0.8) if rng.chance(0.5) else 0.0,
    }
    forces = {
        "gravity_x": rng.uniform(-0.4, 0.4) if rng.chance(0.5) else 0.0,
        "gravity_y": rng.uniform(-0.6, 0.6) if rng.chance(0.5) else 0.0,
        "drag": rng.uniform(0.05, 0.4),
        "central": rng.uniform(0.2, 1.5) if rng.chance(0.6) else 0.0,
        "vortex": rng.uniform(-1.4, 1.4) if rng.chance(0.6) else 0.0,
    }
    turbulence = {
        "amp": rng.uniform(0.4, 1.6) if rng.chance(0.8) else 0.0,
        "freq": rng.uniform(0.6, 2.4),
        "noise_type": rng.choice(["perlin", "simplex", "fbm"]),
        "seed": rng.randint(0, 2**31 - 1),
    }
    return {
        "n_particles": rng.randint(2000, 4000),
        "dt": rng.uniform(0.02, 0.045),
        "life": rng.uniform(20.0, 90.0),
        "color_by": rng.choice(["age", "speed"], weights=[0.65, 0.35]),
        "emitter": emitter,
        "forces": forces,
        "turbulence": turbulence,
        "seed": rng.randint(0, 2**31 - 1),
    }
