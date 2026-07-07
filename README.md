# Moteur d'Art Génératif Mathématique

Un moteur créatif qui génère des œuvres originales à partir d'équations
mathématiques. Chaque œuvre est unique mais appartient à une même famille
visuelle reconnaissable. Une œuvre est entièrement définie par son **génome
mathématique** : une seed suffit à la reconstruire au pixel près.

![galerie](docs/gallery.png)

## Philosophie

- Les équations ne sont **pas codées en dur** : elles sont générées à partir de
  paramètres tirés d'une seed déterministe.
- Une œuvre = un `ArtworkGenome` sérialisable en JSON → reproductibilité totale.
- Un **modèle unifié** : toute famille d'équations produit un nuage de points 2D
  + une valeur de coloration, rendu par accumulation lumineuse. C'est ce qui
  donne à toutes les œuvres une identité de famille commune.

## Installation

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows ;  source .venv/bin/activate sous Unix
pip install -e ".[dev]"
```

Dépendances : Python 3.12+, NumPy, Pillow (Matplotlib pour le prototypage).

## Utilisation

### Ligne de commande

```bash
# Une œuvre depuis une seed (aléatoire si omise)
art-generator gen --seed 42 --size 1600 --out outputs

# Un lot d'œuvres
art-generator batch -n 8 --out outputs

# Re-rendre une œuvre depuis son génome JSON
art-generator render outputs/genome_42.json
```

### API Python

```python
import art_generator as ag

genome, image = ag.render_seed(42)
image.save("oeuvre.png")

# ou pas à pas
genome = ag.generate(seed=42, width=2000, height=2000)
image = ag.Engine().render(genome)
```

### Planche-contact

```bash
python -m art_generator.examples.generate_gallery --seeds 1-16 --tile 400
```

## Architecture

```
art_generator/
├── core/         # génome, RNG déterministe, moteur, fond, modes de fusion
├── equations/    # familles d'équations (registre extensible)
│   ├── parametric.py     courbes paramétriques harmoniques
│   ├── polar.py          roses, rosaces, spirales
│   ├── attractors.py     Clifford, de Jong, attracteurs personnalisés
│   ├── vector_field.py   champs de vecteurs (advection de particules)
│   ├── complex_map.py    transformations conformes du plan complexe
│   └── fractal.py        Mandelbrot / Julia en Buddhabrot (orbites)
├── noise/        # bruits procéduraux : Perlin, fBm, Worley (warp & couleur)
├── generators/   # génération + contrôle de viabilité d'un génome
├── palettes/     # palettes procédurales (cosinus, HSV, dégradés multi-arrêts)
├── renderers/    # accumulation lumineuse + symétries + déformation par bruit
├── exporters/    # export image + sérialisation JSON du génome
├── utils/        # cadrage robuste, nettoyage des singularités
├── presets/      # génomes de référence
└── examples/     # scripts de démonstration
```

**Ajouter une famille d'équations** : implémenter une classe `Equation` et
l'enregistrer dans `equations/registry.py`. Rien d'autre n'a besoin d'être
modifié — ni le moteur, ni le renderer, ni le générateur.

## Reproductibilité

- Même seed → pixels identiques.
- Génome JSON rechargé → œuvre identique.

Ces deux garanties sont couvertes par la suite de tests (`pytest`).

## Feuille de route

Voir [ROADMAP.md](ROADMAP.md) : bruit (Perlin/Simplex/Worley), champs de
vecteurs, domaines complexes, fractales, animation (GIF/MP4), export vectoriel
(SVG/PDF), interface graphique temps réel, accélération GPU.
