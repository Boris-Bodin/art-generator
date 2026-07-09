"""Pont moteur ↔ navigateur, exécuté **dans Pyodide** (WebAssembly).

Chargé par ``app.js`` après l'installation du wheel, ce module expose des
fonctions simples que le JavaScript appelle pour obtenir une image PNG (encodée
en base64) à partir d'un preset ou d'une seed. Toute la logique lourde reste dans
le package ``art_generator`` ; ce fichier ne fait qu'adapter les types (génome →
PNG base64) et fixer les plafonds propres au rendu web.

Contraintes web :

* le rendu tourne côté client en WASM (plus lent que le natif) et la boucle des
  attracteurs est du Python pur — d'où un **plafond de points** (`WEB_POINT_CAP`)
  et une **taille d'aperçu** modérée (`WEB_MAX_SIDE`) pour rester à quelques
  secondes par image ;
* le rendu reste *fidèle* à l'œuvre finale (même densité relative, même palette),
  grâce à l'indépendance à la résolution du moteur.
"""

import base64
import io
import json

from art_generator.generators.genome_generator import generate
from art_generator.presets import library
from art_generator.ui import preview

# Grand côté de l'aperçu (px) et plafond de points par couche. Réglés pour un
# compromis netteté / réactivité en WASM ; ajustables sans toucher au moteur.
WEB_MAX_SIDE = 1600
WEB_POINT_CAP = 150_000


def _png_b64(genome) -> str:
    """Rend un génome en PNG et renvoie ses octets encodés en base64 ASCII."""
    img = preview.render_preview(genome, max_side=WEB_MAX_SIDE, point_cap=WEB_POINT_CAP)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def presets_json() -> str:
    """Catalogue des presets intégrés, en JSON (nom, fichier, description)."""
    return json.dumps(
        [
            {"name": p.name, "file": p.filename, "description": p.description}
            for p in library.builtin_presets()
        ]
    )


def render_preset(name: str) -> str:
    """PNG base64 du preset intégré ``name``."""
    return _png_b64(library.load(name))


def render_seed(seed: int) -> str:
    """PNG base64 de l'œuvre reconstruite depuis ``seed``."""
    return _png_b64(generate(int(seed)))
