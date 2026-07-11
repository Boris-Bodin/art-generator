"""Fractales à temps d'échappement, rendues en nuage de points (Buddhabrot).

Plutôt qu'un rendu par pixel (hors modèle), on accumule les **orbites** des
points qui s'échappent — la technique « Buddhabrot ». Cela conserve le modèle
unifié nuage-de-points et produit des structures fantomatiques caractéristiques.

Variantes :
  * ``mandelbrot`` — ``c`` tiré aléatoirement, ``z0 = 0`` (Buddhabrot classique)
  * ``julia``      — ``c`` fixé, ``z0`` tiré aléatoirement dans le plan

Conformément à la vision, les fractales sont possibles mais ne sont pas le cœur
du projet : c'est une famille parmi d'autres dans le registre.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Equation


class Fractal(Equation):
    """Fractale d'échappement rendue par accumulation d'orbites."""

    family = "fractal"

    def sample(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        p = self.params
        variant = p.get("variant", "mandelbrot")
        max_iter = int(p.get("max_iter", 200))
        # Le Buddhabrot brut dégénère en disque de bruit sans symétrie : les
        # orbites rapides déversent leur position initiale quasi-uniforme (le
        # « carré ») et leur dernier point près du rayon d'échappement 2 (le
        # « cercle »). On corrige ces deux artefacts *sans* décimer la densité
        # (essentielle sous symétrie) :
        #   - ``min_depth`` saute les tout premiers points (la couche uniforme) ;
        #   - ``keep_radius`` écarte la coquille d'échappement (|z| proche de 2),
        #     supprimant le bord circulaire dur tout en gardant l'intérieur.
        # ``min_escape`` (rejet d'orbites entières) reste disponible mais neutre
        # par défaut pour ne pas appauvrir les nuages. Bornés à ``max_iter``.
        min_escape = min(int(p.get("min_escape", 1)), max_iter)
        min_depth = min(int(p.get("min_depth", 1)), max_iter - 1)
        keep_radius = float(p.get("keep_radius", 1.9))
        # Le Buddhabrot exige beaucoup de tirages candidats : seule une fraction
        # s'échappe, et chaque orbite échappée fournit plusieurs points. La borne
        # haute laisse le nuage suivre la montée en résolution (n croît avec
        # l'aire) tout en bornant la mémoire de ``history`` (max_iter x
        # samples complexes) ; en deçà de la référence 1600 px elle n'est pas
        # atteinte, le rendu y est donc inchangé.
        samples = int(np.clip(n // 5, 8000, 300000))

        rng = np.random.default_rng(int(p["seed"]))
        pts = rng.uniform(0, 1, (samples, 2))
        cand = (pts[:, 0] * 3.0 - 2.1) + 1j * (pts[:, 1] * 3.0 - 1.5)

        if variant == "julia":
            c = np.full(samples, complex(p["cx"], p["cy"]))
            z = cand.copy()
        else:  # mandelbrot / buddhabrot
            c = cand
            z = np.zeros(samples, dtype=np.complex128)

        history = np.empty((max_iter, samples), dtype=np.complex128)
        alive = np.ones(samples, dtype=bool)
        escaped_at = np.full(samples, max_iter, dtype=np.int64)

        for i in range(max_iter):
            z = np.where(alive, z * z + c, z)  # on gèle les orbites échappées
            history[i] = z
            newly = alive & (np.abs(z) > 2.0)
            escaped_at[newly] = i
            alive &= ~newly

        escaped = (escaped_at < max_iter) & (escaped_at >= min_escape)
        depth = np.arange(max_iter)[:, None]
        valid = escaped[None, :] & (depth >= min_depth) & (depth < escaped_at[None, :])

        orbit = history[valid]
        values = np.clip(np.broadcast_to(depth, valid.shape)[valid] / max_iter, 0.0, 1.0)
        if keep_radius < 2.0:  # retire la coquille d'échappement (bord circulaire)
            inside = np.abs(orbit) <= keep_radius
            orbit = orbit[inside]
            values = values[inside]
        points = np.column_stack((orbit.real, orbit.imag))
        return points, values


def default_params(rng) -> dict[str, Any]:
    variant = rng.choice(["mandelbrot", "julia"], weights=[0.5, 0.5])
    return {
        "variant": variant,
        "max_iter": rng.randint(80, 240),
        "cx": rng.uniform(-0.8, 0.4),
        "cy": rng.uniform(-0.8, 0.8),
        "seed": rng.randint(0, 2**31 - 1),
    }
