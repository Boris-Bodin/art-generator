"""Interface en ligne de commande du moteur d'art génératif.

Exemples :

    art-generator gen --seed 42 --size 1600 --out outputs
    art-generator gen                       # seed aléatoire
    art-generator batch -n 8 --out outputs  # plusieurs œuvres
    art-generator render outputs/genome_42.json
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .core.engine import Engine
from .exporters import genome_io, image
from .generators.genome_generator import generate


def _render_and_save(genome, out_dir: Path, dpi: int) -> tuple[Path, Path]:
    engine = Engine()
    img = engine.render(genome)
    stem = f"genome_{genome.seed}"
    img_path = image.save_image(img, out_dir / f"{stem}.png", dpi=dpi)
    json_path = genome_io.save(genome, out_dir / f"{stem}.json")
    return img_path, json_path


def _cmd_gen(args: argparse.Namespace) -> int:
    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    genome = generate(seed, width=args.size, height=args.size)
    img_path, json_path = _render_and_save(genome, Path(args.out), args.dpi)
    print(f"Œuvre  : {img_path}")
    print(f"Génome : {json_path}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    start = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    for i in range(args.count):
        seed = start + i
        genome = generate(seed, width=args.size, height=args.size)
        img_path, _ = _render_and_save(genome, out_dir, args.dpi)
        print(f"[{i + 1}/{args.count}] seed={seed} -> {img_path}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    genome = genome_io.load(args.genome)
    img = Engine().render(genome)
    out = args.out or Path(args.genome).with_suffix(".png")
    path = image.save_image(img, out, dpi=args.dpi)
    print(f"Œuvre : {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="art-generator",
        description="Moteur d'art génératif mathématique.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gen", help="Générer et rendre une œuvre depuis une seed.")
    g.add_argument("--seed", type=int, default=None, help="Seed (aléatoire si omise).")
    g.add_argument("--size", type=int, default=1600, help="Côté de l'image en pixels.")
    g.add_argument("--dpi", type=int, default=300)
    g.add_argument("--out", default="outputs", help="Dossier de sortie.")
    g.set_defaults(func=_cmd_gen)

    b = sub.add_parser("batch", help="Générer plusieurs œuvres consécutives.")
    b.add_argument("-n", "--count", type=int, default=8)
    b.add_argument("--seed", type=int, default=None, help="Seed de départ.")
    b.add_argument("--size", type=int, default=1200)
    b.add_argument("--dpi", type=int, default=300)
    b.add_argument("--out", default="outputs")
    b.set_defaults(func=_cmd_batch)

    r = sub.add_parser("render", help="Recharger un génome JSON et le rendre.")
    r.add_argument("genome", help="Chemin du fichier .json.")
    r.add_argument("--out", default=None)
    r.add_argument("--dpi", type=int, default=300)
    r.set_defaults(func=_cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
