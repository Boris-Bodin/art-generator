"""Export temporel : un génome animé → GIF, MP4 ou séquence PNG.

Chaque frame ne dépend que de ``(genome, t)`` (via ``animation.evaluate``), donc
le rendu est **embarrassingly parallel** : on réutilise le ``ProcessPoolExecutor``
comme la planche-contact (ordre des frames préservé, fallback séquentiel).

Formats :

* **GIF** et **séquence PNG** : via Pillow, **aucune dépendance nouvelle** ;
* **MP4** : via ``imageio``/``imageio-ffmpeg`` (import paresseux, dépendance
  optionnelle), meilleure qualité que le GIF (limité à 256 couleurs).

Les frames sont rendues par le moteur inchangé : tiling, indépendance à la
résolution et déterminisme sont hérités tels quels.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
from pathlib import Path
from typing import Iterator

from PIL import Image

from ..core.animation import color_cycle_track, evaluate, frame_time
from ..core.engine import Engine
from ..core.genome import AnimationGenome, ArtworkGenome, Keyframe, Track


def default_spin_animation(
    genome: ArtworkGenome, frames: int = 90, fps: int = 30
) -> AnimationGenome:
    """Animation « de démonstration » quand le génome n'en porte aucune.

    Fait tourner l'orientation du fond **et cycle la couleur de chaque couche**
    sur un tour complet (boucle sans couture). Le cyclage s'adapte au mode de
    palette : la **teinte** (``hue``) pour hsv/hsl, la **phase** du gradient
    cosinus sinon — de sorte que le *sujet* s'anime visiblement quelle que soit
    l'œuvre (et pas seulement le fond).
    """
    tau = 6.283185307179586
    tracks = [Track("background_params.angle", [Keyframe(0.0, 0.0), Keyframe(1.0, tau)])]
    for i, layer in enumerate(genome.layers):
        tracks.append(color_cycle_track(i, layer))  # gère hsv/hsl/cosine/gradient
    return AnimationGenome(fps=fps, frames=frames, loop=True, tracks=tracks)


def _ensure_animation(genome: ArtworkGenome) -> AnimationGenome:
    if genome.animation is not None:
        return genome.animation
    return default_spin_animation(genome)


# Fonction de niveau module (picklable) exécutée dans les process workers.
def _render_frame(genome: ArtworkGenome, t: float, tile: str) -> Image.Image:
    return Engine().render(evaluate(genome, t), tile=tile)


def _resolve_jobs(jobs: int | None, n_frames: int) -> int:
    if jobs is None:
        jobs = os.cpu_count() or 1
    return max(1, min(jobs, n_frames))


def iter_frames(
    genome: ArtworkGenome,
    jobs: int | None = None,
    tile: str = "auto",
    progress: "callable | None" = None,
) -> Iterator[Image.Image]:
    """Itère les frames de l'animation, dans l'ordre, éventuellement en parallèle.

    Utilise ``genome.animation`` ; à défaut, une animation « spin » par défaut.
    Les frames sortent **en ordre** (``ProcessPoolExecutor.map`` le garantit), ce
    qui permet de les écrire au fil de l'eau (MP4, PNG) sans tout charger en RAM.

    ``progress`` (optionnel) est appelé ``progress(done, total)`` après chaque
    frame — utile pour une barre d'avancement dans l'UI.
    """
    animation = _ensure_animation(genome)
    times = [frame_time(animation, i) for i in range(max(1, animation.frames))]
    total = len(times)
    effective = _resolve_jobs(jobs, total)

    def _emit(source):
        for done, img in enumerate(source, start=1):
            if progress is not None:
                progress(done, total)
            yield img

    if effective <= 1:
        yield from _emit(_render_frame(genome, t, tile) for t in times)
        return
    with ProcessPoolExecutor(max_workers=effective) as pool:
        yield from _emit(pool.map(_render_frame, repeat(genome), times, repeat(tile)))


# --- écrivains --------------------------------------------------------------


def save_gif(
    genome: ArtworkGenome, path: str | Path, jobs: int | None = None,
    progress: "callable | None" = None,
) -> Path:
    """Écrit un GIF animé (Pillow, 256 couleurs, palette adaptative par frame)."""
    animation = _ensure_animation(genome)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [
        img.convert("P", palette=Image.ADAPTIVE)
        for img in iter_frames(genome, jobs=jobs, progress=progress)
    ]
    duration = round(1000.0 / max(1, animation.fps))
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0 if animation.loop else 1,
        disposal=2,
        optimize=False,
    )
    return path


def save_png_sequence(
    genome: ArtworkGenome, out_dir: str | Path, jobs: int | None = None, dpi: int = 300,
    progress: "callable | None" = None,
) -> Path:
    """Écrit une séquence ``frame_0001.png`` … dans ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(iter_frames(genome, jobs=jobs, progress=progress), start=1):
        img.save(out_dir / f"frame_{i:04d}.png", dpi=(dpi, dpi))
    return out_dir


def save_mp4(
    genome: ArtworkGenome, path: str | Path, jobs: int | None = None,
    progress: "callable | None" = None,
) -> Path:
    """Écrit un MP4 (H.264) via ``imageio``/``imageio-ffmpeg`` (dépendance optionnelle)."""
    try:
        import imageio.v2 as imageio  # import paresseux : dépendance optionnelle
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "L'export MP4 nécessite « imageio » et « imageio-ffmpeg ». "
            "Installez-les (pip install imageio imageio-ffmpeg) ou exportez en GIF/PNG."
        ) from exc

    import numpy as np

    animation = _ensure_animation(genome)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # macro_block_size=None : ne force pas les dimensions à un multiple de 16.
    writer = imageio.get_writer(path, fps=animation.fps, macro_block_size=None)
    try:
        for img in iter_frames(genome, jobs=jobs, progress=progress):
            writer.append_data(np.asarray(img))
    finally:
        writer.close()
    return path


_DISPATCH = {".gif": save_gif, ".mp4": save_mp4, ".webm": save_mp4}


def save_animation(
    genome: ArtworkGenome, path: str | Path, jobs: int | None = None, dpi: int = 300,
    progress: "callable | None" = None,
) -> Path:
    """Écrit l'animation ; le format découle de l'extension.

    ``.gif`` → GIF · ``.mp4``/``.webm`` → vidéo · sinon → séquence PNG (dossier).
    """
    path = Path(path)
    writer = _DISPATCH.get(path.suffix.lower())
    if writer is save_mp4:
        return save_mp4(genome, path, jobs=jobs, progress=progress)
    if writer is save_gif:
        return save_gif(genome, path, jobs=jobs, progress=progress)
    return save_png_sequence(genome, path, jobs=jobs, dpi=dpi, progress=progress)
