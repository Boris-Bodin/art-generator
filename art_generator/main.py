"""Interface en ligne de commande du moteur d'art génératif.

Exemples :

    art-generator gen --seed 42 --size 1600 --out outputs
    art-generator gen --seed 42 --preset 4k --ratio 16:9        # 3840x2160
    art-generator gen --seed 42 --preset 8k --format svg        # export vectoriel
    art-generator gen                       # seed aléatoire
    art-generator batch -n 8 --out outputs  # plusieurs œuvres
    art-generator render outputs/genome_42.json --preset 16k    # re-rendu 16K (tuiles auto)
    art-generator render outputs/genome_42.json --out oeuvre.pdf
    art-generator anim --seed 42 --frames 90 --format gif       # animation (spin par défaut)
    art-generator anim genome_42.json --format mp4 --jobs 8      # vidéo parallèle
    art-generator ui --seed 42              # éditeur graphique, aperçu temps réel
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


def _cmd_recover_seed(args: argparse.Namespace) -> int:
    from .generators.recover import recover_seed

    genome = genome_io.load(args.genome)
    if genome.title:
        print(f"Titre présent : « {genome.title} » (encode souvent la seed).")

    def _progress(seed: int) -> None:
        print(f"  … seed {seed}", end="\r", file=sys.stderr, flush=True)

    result = recover_seed(genome, start=args.start, stop=args.stop, on_progress=_progress)
    print(" " * 40, end="\r", file=sys.stderr)  # efface la ligne de progression
    if result.found:
        print(f"Seed retrouvée : {result.seed}  ({result.tried} candidats testés)")
        return 0
    print(
        f"Aucune seed dans [{args.start}, {args.stop}) ne reproduit ce génome "
        f"({result.tried} candidats testés)."
    )
    return 1


def _cmd_anim(args: argparse.Namespace) -> int:
    from .exporters import animation

    # Une séquence PNG s'écrit dans un **dossier** ; GIF/MP4 dans un fichier.
    is_sequence = args.format.lower() not in ("gif", "mp4", "webm")

    if args.genome:
        genome = genome_io.load(args.genome)
        if args.preset is not None or args.size is not None:
            genome.width, genome.height = _dimensions(args, default_size=genome.width)
        stem = Path(args.genome).with_suffix("")
        default_out = stem if is_sequence else stem.with_suffix(f".{args.format}")
    else:
        from .generators.genome_generator import generate

        seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
        width, height = _dimensions(args, default_size=1600)
        genome = generate(seed, width=width, height=height)
        base = Path(args.out) / f"anim_{seed}"
        default_out = base if is_sequence else base.with_suffix(f".{args.format}")

    # Réglages temporels : posés sur l'animation du génome, ou sur celle par défaut.
    if genome.animation is None:
        genome.animation = animation.default_spin_animation(args.frames, args.fps)
        print("Aucune animation dans le génome : animation « spin » par défaut.")
    else:
        genome.animation.frames = args.frames
        genome.animation.fps = args.fps

    out = Path(args.output) if args.output else default_out
    path = animation.save_animation(genome, out, jobs=args.jobs, dpi=args.dpi)
    print(
        f"Animation : {path}  ({genome.width}x{genome.height}, "
        f"{genome.animation.frames} frames @ {genome.animation.fps} fps)"
    )
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    from .ui.app import launch  # import paresseux (Tkinter)

    return launch(seed=args.seed)


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

    rs = sub.add_parser(
        "recover-seed",
        help="Retrouver par force brute la seed d'un génome JSON (champ seed perdu).",
    )
    rs.add_argument("genome", help="Chemin du fichier .json.")
    rs.add_argument("--start", type=int, default=0, help="Début de l'intervalle de seeds.")
    rs.add_argument(
        "--stop", type=int, default=100_000, help="Fin (exclue) de l'intervalle de seeds."
    )
    rs.set_defaults(func=_cmd_recover_seed)

    a = sub.add_parser(
        "anim", help="Rendre une animation (GIF/MP4/séquence PNG) depuis un génome ou une seed."
    )
    a.add_argument("genome", nargs="?", default=None, help="Chemin d'un .json (optionnel).")
    a.add_argument("--seed", type=int, default=None, help="Seed si aucun génome fourni.")
    a.add_argument("--frames", type=int, default=90, help="Nombre de frames.")
    a.add_argument("--fps", type=int, default=30, help="Images par seconde.")
    a.add_argument("--output", "-o", default=None, help="Fichier de sortie (.gif/.mp4) ou dossier PNG.")
    a.add_argument(
        "--jobs", type=int, default=None,
        help="Process workers en parallèle (défaut : nombre de cœurs ; 1 = séquentiel).",
    )
    _add_resolution_args(a, default_size=None)
    a.add_argument("--out", default="outputs", help="Dossier de sortie (si seed).")
    a.set_defaults(func=_cmd_anim)

    u = sub.add_parser("ui", help="Ouvrir l'éditeur graphique (aperçu temps réel).")
    u.add_argument("--seed", type=int, default=None, help="Seed de départ (aléatoire si omise).")
    u.set_defaults(func=_cmd_ui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
