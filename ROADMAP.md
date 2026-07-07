# Feuille de route

La Phase 1 pose des fondations propres et un moteur qui produit déjà des œuvres.
Les phases suivantes enrichissent le langage artistique sans casser l'interface
(génome sérialisable, registre d'équations, modèle « nuage de points »).

## Phase 1 — Fondations ✅ (livré)

- [x] `ArtworkGenome` sérialisable (JSON), reproductible au pixel près
- [x] RNG déterministe (PCG64)
- [x] Familles : courbes paramétriques, polaires, attracteurs (Clifford, de Jong, custom)
- [x] Générateur d'équations avec contrôle de viabilité (rejet des formes dégénérées)
- [x] Palettes procédurales (gradient cosinus)
- [x] Renderer par accumulation lumineuse (HDR, glow, compression tonale)
- [x] Symétries : miroir, radiale, kaléidoscope
- [x] Couches multiples + modes de fusion (normal, add, screen, multiply, difference)
- [x] Fonds : noir, blanc, dégradé
- [x] Export PNG/TIFF, CLI, planche-contact
- [x] Suite de tests (déterminisme, round-trip, viabilité)

## Phase 2 — Richesse du langage ✅ (livré)

- [x] **Bruit** (`noise/fields.py`) : Perlin, fBm (somme fractale), Worley,
      appliqué en déformation du domaine (warp) et en modulation des couleurs
      via les champs `noise_type`/`warp`/`warp_freq`/`color_noise` de la couche
- [x] **Champs de vecteurs** (`equations/vector_field.py`) : `dx/dt = f(x,y)`,
      `dy/dt = g(x,y)` avec advection de particules le long des lignes de courant
- [x] **Domaines complexes** (`equations/complex_map.py`) : transformations
      conformes `w = f(z)` itérées (poly / sinus / rationnelle de type Möbius)
- [x] **Fractales** (`equations/fractal.py`) : Mandelbrot & Julia rendus en
      **Buddhabrot** (accumulation d'orbites) pour rester dans le modèle nuage de
      points ; famille parmi d'autres, non centrale
- [x] Palettes **HSV** et **dégradés multi-arrêts** (`palettes/procedural.py`)

## Phase 2+ — Compléments ✅ (livré)

- [x] Bruit **Simplex** 2D véritable (`noise/fields.py::simplex2d`), grille de
      triangles sans artefacts directionnels
- [x] Bruit modulant aussi **la lumière** (poids lumineux par point) et
      **l'épaisseur** (rayon de trait par point) — champs `light_noise` et
      `thickness_noise` de la couche, appliqués dans l'accumulation
- [x] Palettes **HSL** (`palettes/procedural.py::hsl_palette`)
- [x] **Contraintes d'harmonie** (`harmonic_palette`) : schémas de la roue
      chromatique (monochrome, analogue, complémentaire, split-complémentaire,
      triadique, tétradique) — harmonie garantie par construction
- [x] **Palettes nommées** (`NAMED_PALETTES` : nebula, ember, aurora, bio,
      ocean, sunset) pour une direction artistique reconnaissable

  Reste ouvert : bruit 3D pour l'animation temporelle (Phase 4).

## Phase 3 — Système de particules

- [ ] Particules avec position, vitesse, couleur, durée de vie, taille, opacité
- [ ] Passage à l'échelle : centaines de milliers → millions de particules
- [ ] Émetteurs, forces, turbulence pilotés par le génome

## Phase 4 — Animation & export

- [ ] Animation des paramètres, couleurs, particules, équations (keyframes)
- [ ] Export GIF, MP4, séquences PNG
- [ ] Export vectoriel SVG/PDF (rendu par tracés, via CairoSVG)
- [ ] Résolutions HD/4K/8K/16K, DPI configurable, rendu par tuiles

## Phase 5 — Interface & performance

- [ ] Interface graphique moderne : édition des paramètres, changement de seed,
      visualisation temps réel, sauvegarde/chargement d'œuvres
- [ ] Bibliothèque de presets et navigation dans l'espace des génomes
- [ ] Optimisation : vectorisation poussée, multiprocessing
- [ ] Accélération GPU (OpenGL/Vulkan/GLSL, Numba/CUDA) sur les points chauds
      (itération des attracteurs, accumulation, advection de particules)

## Dette technique connue

- L'itération des attracteurs est une boucle Python (correcte mais limitée à
  quelques centaines de milliers de points par couche) — candidate n°1 au GPU.
- Le contrôle de viabilité peut laisser passer des formes quasi 1D ; un critère
  de « surface minimale » plus fin est envisageable.
