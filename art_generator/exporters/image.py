"""Export d'images.

Formats matriciels pris en charge via Pillow (PNG, TIFF, JPEG…). Le SVG/PDF
vectoriel est prévu dans la feuille de route (rendu par tracés plutôt que par
accumulation).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def save_image(image: Image.Image, path: str | Path, dpi: int = 300) -> Path:
    """Enregistre l'image ; le format découle de l'extension du fichier."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    params = {}
    if path.suffix.lower() in {".png", ".tif", ".tiff", ".jpg", ".jpeg"}:
        params["dpi"] = (dpi, dpi)
    image.save(path, **params)
    return path
