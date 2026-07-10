# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environnement & commandes

Python n'est **pas** sur le PATH global : utiliser l'interpréteur du venv, `.venv/Scripts/python.exe`. Le package est installé en mode éditable, donc `import art_generator` fonctionne depuis la racine sans `PYTHONPATH`.

```bash
.venv/Scripts/python.exe -m pytest -q                 # toute la suite
.venv/Scripts/python.exe -m pytest tests/test_engine.py::test_json_round_trip_is_pixel_identical   # un seul test
.venv/Scripts/python.exe -m art_generator.main gen --seed 42 --size 1600 --out outputs
.venv/Scripts/python.exe -m art_generator.main render <genome.json>     # re-rendre depuis un JSON
.venv/Scripts/python.exe -m art_generator.examples.generate_gallery --seeds 1-16
```

Le point d'entrée console `art-generator` (défini dans `pyproject.toml`) mappe vers `art_generator.main:main`.

## Idées directrices

Trois invariants structurent tout le moteur — les casser est presque toujours un bug :

1. **Une œuvre = un génome.** Toute œuvre est entièrement définie par un `ArtworkGenome` (`core/genome.py`), composé de dataclasses sérialisables. Une seed → un génome → une image. Deux garanties, couvertes par les tests : même seed → pixels identiques, et round-trip JSON (`exporters/genome_io.py`) → pixels identiques. **Toute source d'aléa doit passer par `core/rng.py` (`RNG`, PCG64)** ; un `random`/`np.random` direct casse la reproductibilité.

2. **Modèle unifié « nuage de points ».** *Toute* famille d'équations, quelle qu'elle soit, implémente `equations/base.py::Equation.sample(n) -> (points[N,2], values[N] in [0,1])`. Les points bruts peuvent contenir des NaN/inf (singularités) : ils sont filtrés en aval, pas dans l'équation. C'est ce dénominateur commun qui permet à un unique renderer de donner une identité visuelle partagée à des familles très différentes.

3. **Le registre est le seul point d'extension.** `equations/registry.py` mappe un nom de famille → (classe `Equation`, fabrique de paramètres depuis un `RNG`). **Ajouter une famille = écrire une classe `Equation` + un `default_params(rng)` + `register(...)`.** Ni le moteur, ni le renderer, ni le générateur, ni la sérialisation n'ont besoin d'être modifiés.

## Pipeline de rendu

`core/engine.py::Engine.render(genome)` orchestre, sans connaître les familles ni les détails de rendu :

1. Fond (`core/background.py`) → tampon HDR `(H,W,3)`.
2. Pour chaque couche : `registry.build()` l'équation, puis `renderers/accumulation.py::render_layer()`.
3. Composition des couches via `core/blend.py` (normal/add/screen/multiply/difference + opacité).

`render_layer` enchaîne un ordre précis (à respecter si on le modifie) : `sample` → nettoyage des singularités → **centrage** sur la médiane → **symétrie** (`renderers/symmetry.py`, sur points centrés pour des rotations correctes) → **cadrage robuste** par percentiles (`utils/math_utils.py::fit_to_canvas`, préserve le ratio d'aspect) → couleur (`palettes/procedural.py`, gradient cosinus calculé, jamais listé) → **accumulation** additive (`np.add.at`) → **compression tonale** log + normalisation par percentile + **glow** (flou gaussien).

## Génération & viabilité

`generators/genome_generator.py` tire un génome complet depuis une seed (familles, couches, palettes apparentées, symétrie, fond). Point crucial : `generators/quality.py` **rejette les formes dégénérées** (attracteurs qui s'effondrent en un point, courbes quasi-plates) en rasterisant un échantillon sur une grille et en exigeant une occupation minimale. Le rejet est déterministe (piloté par le `RNG`), donc reproductible. Sans ce filtre, beaucoup de seeds produisent des images noires.

## Attendus du projet

- Code orienté objet, dataclasses quand pertinent, méthodes typées et documentées.
- Voir `ROADMAP.md` pour les phases suivantes (bruit, champs de vecteurs, domaines complexes, fractales, particules, animation, export SVG/PDF, UI, GPU). La dette n°1 : l'itération des attracteurs est une boucle Python (`equations/attractors.py`), candidate à l'accélération GPU — l'interface `Equation.sample` est conçue pour ne pas changer lors de ce portage.

## Flux de travail

- **Ne pas utiliser de worktree** : éditer et commiter directement sur la branche principale (l'isolation en job de fond est désactivée via `.claude/settings.json`).
- Suivre les conventions de commit et les interdits définis dans le CLAUDE.md global (Conventional Commits, **aucune signature IA** dans les commits, PR ou merge requests).
