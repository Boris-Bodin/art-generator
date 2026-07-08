"""Interface en ligne de commande du moteur d'art génératif.

Exemples :

    art-generator gen --seed 42 --size 1600 --out outputs
    art-generator gen --seed 42 --preset 4k --ratio 16:9        # 3840x2160
    art-generator gen --seed 42 --preset 8k --format svg        # export vectoriel
    art-generator gen                       # seed aléatoire
    art-generator batch -n 8 --out outputs  # plusieurs œuvres
    art-generator render outputs/genome_42.json --preset 16k    # re-rendu 16K (tuiles auto)
    art-generator render outputs/genome_42.json --out oeuvre.pdf
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .core.engine import Engine
from .exporters import genome_io, image, resolution

_VECTOR_SUFFIXES = {".svg", ".pdf"}


def _dimensions(args: argparse.Namespace, default_size: int) -> tuple[int, int]:
    """Traduit les options de résolution en ``(width, height)`` pixels."""
    preset = getattr(args, "preset", None)
    ratio = getattr(args, "ratio", None)
    size = getattr(args, "size", None)
    if preset is None and size is None:
        size = default_size
    return resolution.resolve_dimensions(preset=preset, ratio=ratio, size=size)


def _save_artwork(genome, out_path: Path, dpi: int, tile: str) -> Path:
    """Rend puis enregistre l'œuvre ; le format découle de l'extension.

    ``.svg``/``.pdf`` déclenchent l'export **vectoriel** (par tracés) ; tout
    autre suffixe passe par le rendu matriciel (avec tuiles automatiques pour les
    très grandes résolutions).
    """
    out_path = Path(out_path)
    if out_path.suffix.lower() in _VECTOR_SUFFIXES:
        from .exporters import vector  # import paresseux (matplotlib)

        return vector.save_vector(genome, out_path, dpi=dpi)
    img = Engine().render(genome, tile=tile)
    return image.save_image(img, out_path, dpi=dpi)


def _cmd_gen(args: argparse.Namespace) -> int:
    from .generators.genome_generator import generate

    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    width, height = _dimensions(args, default_size=1600)
    genome = generate(seed, width=width, height=height)
    stem = f"genome_{seed}"
    img_path = _save_artwork(genome, Path(args.out) / f"{stem}.{args.format}", args.dpi, args.tile)
    json_path = genome_io.save(genome, Path(args.out) / f"{stem}.json")
    print(f"Œuvre  : {img_path}  ({width}x{height})")
    print(f"Génome : {json_path}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    from .generators.genome_generator import generate

    out_dir = Path(args.out)
    width, height = _dimensions(args, default_size=1200)
    start = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    for i in range(args.count):
        seed = start + i
        genome = generate(seed, width=width, height=height)
        img_path = _save_artwork(
            genome, out_dir / f"genome_{seed}.{args.format}", args.dpi, args.tile
        )
        genome_io.save(genome, out_dir / f"genome_{seed}.json")
        print(f"[{i + 1}/{args.count}] seed={seed} -> {img_path}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    genome = genome_io.load(args.genome)
    # Ré-cadrage optionnel à une autre résolution (préréglage ou taille).
    if args.preset is not None or args.size is not None:
        genome.width, genome.height = _dimensions(args, default_size=genome.width)
    out = Path(args.out) if args.out else Path(args.genome).with_suffix(f".{args.format}")
    path = _save_artwork(genome, out, args.dpi, args.tile)
    print(f"Œuvre : {path}  ({genome.width}x{genome.height})")
    return 0


def _add_resolution_args(parser: argparse.ArgumentParser, default_size: int | None) -> None:
    parser.add_argument(
        "--preset",
        choices=sorted(resolution.PRESETS),
        default=None,
        help="Préréglage de résolution (grand côté). Prioritaire sur --size.",
    )
    parser.add_argument(
        "--ratio",
        default=None,
        help="Rapport d'aspect, ex. 16:9, 3:2, 4:5. Prime sur le ratio du préréglage ; "
        "défaut : ratio du préréglage sinon 1:1.",
    )
    parser.add_argument(
        "--size", type=int, default=default_size, help="Côté de l'image carrée en pixels."
    )
    parser.add_argument(
        "--tile",
        default="auto",
        help="Rendu par tuiles : 'auto' (selon taille), 'off', ou hauteur de bande en px.",
    )
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--format", default="png", help="Format de sortie : png, tiff, jpg, svg, pdf."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="art-generator",
        description="Moteur d'art génératif mathématique.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gen", help="Générer et rendre une œuvre depuis une seed.")
    g.add_argument("--seed", type=int, default=None, help="Seed (aléatoire si omise).")
    _add_resolution_args(g, default_size=None)
    g.add_argument("--out", default="outputs", help="Dossier de sortie.")
    g.set_defaults(func=_cmd_gen)

    b = sub.add_parser("batch", help="Générer plusieurs œuvres consécutives.")
    b.add_argument("-n", "--count", type=int, default=8)
    b.add_argument("--seed", type=int, default=None, help="Seed de départ.")
    _add_resolution_args(b, default_size=None)
    b.add_argument("--out", default="outputs")
    b.set_defaults(func=_cmd_batch)

    r = sub.add_parser("render", help="Recharger un génome JSON et le rendre.")
    r.add_argument("genome", help="Chemin du fichier .json.")
    r.add_argument("--out", default=None)
    _add_resolution_args(r, default_size=None)
    r.set_defaults(func=_cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
