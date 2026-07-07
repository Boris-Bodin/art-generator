"""Génère une planche-contact de plusieurs œuvres.

Usage :
    python -m art_generator.examples.generate_gallery --seeds 1-16 --tile 400
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from ..core.engine import Engine
from ..generators.genome_generator import generate


def _parse_seeds(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",")]


def build_gallery(seeds: list[int], tile: int, cols: int) -> Image.Image:
    engine = Engine()
    rows = (len(seeds) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * tile), "black")
    for idx, seed in enumerate(seeds):
        genome = generate(seed, width=tile, height=tile)
        img = engine.render(genome)
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
    args = parser.parse_args()

    seeds = _parse_seeds(args.seeds)
    sheet = build_gallery(seeds, args.tile, args.cols)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"Galerie : {args.out}")


if __name__ == "__main__":
    main()
