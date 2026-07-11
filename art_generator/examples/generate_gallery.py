"""Génère une planche-contact de plusieurs œuvres.

Usage :
    python -m art_generator.examples.generate_gallery --seeds 1-16 --tile 400
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
from pathlib import Path

from PIL import Image

from ..core.engine import Engine
from ..generators.genome_generator import generate


def _parse_seeds(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",")]


def _render_tile(seed: int, tile: int) -> Image.Image:
    """Rend une œuvre carrée depuis sa seed.

    Fonction de niveau module (donc picklable) exécutée dans les process workers.
    Chaque tuile est **indépendante** : le rendu ne dépend que de la seed, si
    bien que le résultat est identique au pixel près quel que soit le nombre de
    workers.
    """
    genome = generate(seed, width=tile, height=tile)
    return Engine().render(genome)


def _resolve_jobs(jobs: int | None, n_seeds: int) -> int:
    """Nombre de process workers effectif (borné au nombre de tuiles et de cœurs)."""
    if jobs is None:
        jobs = os.cpu_count() or 1
    return max(1, min(jobs, n_seeds))


def _render_all(seeds: list[int], tile: int, jobs: int | None) -> list[Image.Image]:
    """Rend toutes les tuiles, en parallèle sur plusieurs process si ``jobs > 1``.

    ``ProcessPoolExecutor.map`` **préserve l'ordre** des seeds ; le fallback
    séquentiel (une seule tuile ou ``jobs <= 1``) évite le coût de démarrage des
    workers quand le parallélisme n'apporte rien.
    """
    effective = _resolve_jobs(jobs, len(seeds))
    if effective <= 1:
        return [_render_tile(seed, tile) for seed in seeds]
    with ProcessPoolExecutor(max_workers=effective) as pool:
        return list(pool.map(_render_tile, seeds, repeat(tile)))


def build_gallery(
    seeds: list[int], tile: int, cols: int, jobs: int | None = None
) -> Image.Image:
    rows = (len(seeds) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * tile), "black")
    for idx, (seed, img) in enumerate(zip(seeds, _render_all(seeds, tile, jobs))):
        x = (idx % cols) * tile
        y = (idx // cols) * tile
        sheet.paste(img, (x, y))
        print(f"seed={seed} placé en ({x}, {y})")
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser(description="Planche-contact d'œuvres.")
    parser.add_argument("--seeds", default="1-16", help="ex: 1-16 ou 3,7,42")
    parser.add_argument("--tile", type=int, default=400)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--out", default="outputs/gallery.png")
    parser.add_argument(
        "--jobs", type=int, default=None,
        help="process workers en parallèle (défaut : nombre de cœurs ; 1 = séquentiel)",
    )
    args = parser.parse_args()

    seeds = _parse_seeds(args.seeds)
    sheet = build_gallery(seeds, args.tile, args.cols, args.jobs)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"Galerie : {args.out}")


if __name__ == "__main__":
    main()
