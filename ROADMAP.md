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

## Phase 3 — Système de particules ✅ (livré)

- [x] **Particules** (`equations/particles.py`) avec position, vitesse, durée de
      vie et âge ; simulation pas à pas (intégration d'Euler) enregistrant la
      position de chaque particule à chaque pas → reste dans le modèle unifié
      « nuage de points », donc rendue par le renderer existant sans modification.
      La couleur (âge le long de la trajectoire ou vitesse), l'épaisseur et
      l'opacité proviennent des champs de couche déjà en place (`color_*`,
      `thickness*`, `opacity`).
- [x] **Passage à l'échelle** : le nombre de points demandé pilote le nombre de
      pas (`steps = n // n_particles`) — quelques milliers de particules
      simultanées suffisent à atteindre le million de points.
- [x] **Émetteurs** (point, disque, anneau, ligne), **forces** (gravité,
      attraction/répulsion centrale, tourbillon, traînée) et **turbulence** par
      bruit *curl* (sans divergence) — tout piloté par le génome ; renaissance
      des particules mortes à l'émetteur pour un flux continu.

  Reste ouvert : advection GPU (voir dette technique) et taille/opacité par
  particule variables dans le temps (Phase 4, animation).

## Phase 4 — Composition & fonds

Aujourd'hui le rendu est un « light painting » **additif** : chaque couche vaut
noir là où il n'y a pas de forme, ce qui rend le fond noir quasi obligatoire (en
mode `normal` la couche remplace le fond ; sur fond clair une forme lumineuse se
lave). L'objet de cette phase est de **découpler la forme du fond** et d'élargir
les fonds et le cadrage — sans casser les invariants (seed→pixels identiques,
round-trip JSON). Tout nouveau paramètre passe par le génome et est tiré par
`generators/genome_generator.py`.

- [ ] **4a — Compositing par alpha** : `render_layer` expose une couverture
      (alpha) dérivée de la densité `acc_w` (déjà calculée dans
      `renderers/accumulation.py`) ; l'engine compose la couche sur le fond via
      cet alpha, de sorte que les zones vides laissent transparaître le fond
      quel qu'il soit (fin du fond noir implicite).
- [ ] **4b — Mode « encre sur papier » (soustractif)** : second modèle de rendu
      où le pigment *assombrit* le support au lieu d'ajouter de la lumière, pour
      des formes sombres lisibles sur fond clair. Choix du modèle (additif /
      encre) porté par le génome, à côté de l'additif existant.
- [ ] **4c — Fonds enrichis** (`core/background.py`) : uni, dégradés
      directionnels et **radiaux**, éventuellement vignette ; au-delà des
      `black`/`white`/`gradient` actuels.
- [ ] **4d — Cadrage par densité** (`utils/math_utils.py::fit_to_canvas`) :
      centrer/mettre à l'échelle sur le **centroïde pondéré par la densité**
      (là où il y a le plus de points) plutôt que sur le milieu de la boîte des
      percentiles, pour cadrer sur le cœur de la forme.

## Phase 5 — Performance

- [ ] Optimisation : vectorisation poussée, multiprocessing
- [ ] Accélération GPU (OpenGL/Vulkan/GLSL, Numba/CUDA) sur les points chauds
      (itération des attracteurs, accumulation, advection de particules)
- [ ] **Viabilité affinée** : critère de « surface minimale » plus fin pour
      rejeter les formes quasi 1D que le contrôle actuel laisse passer
      (`generators/quality.py`).

## Phase 6 — Export

- [ ] Export vectoriel SVG/PDF (rendu par tracés, via CairoSVG)
- [ ] Résolutions HD/4K/8K/16K, DPI configurable, rendu par tuiles (profite de
      la performance de la Phase 5)

## Phase 7 — Interface & navigation

- [ ] Interface graphique moderne : édition des paramètres, changement de seed,
      visualisation temps réel, sauvegarde/chargement d'œuvres
- [ ] Bibliothèque de presets et navigation dans l'espace des génomes

## Phase 8 — Animation

- [ ] Animation des paramètres, couleurs, particules, équations (keyframes)
- [ ] **Bruit 3D** (dimension temporelle) pour une animation cohérente des
      champs de bruit (laissé ouvert en Phase 2+)
- [ ] **Particules variables dans le temps** : taille et opacité par particule
      évoluant au fil de la vie (laissé ouvert en Phase 3)
- [ ] Export temporel : GIF, MP4, séquences PNG

## Dette technique connue

- L'itération des attracteurs **et l'advection des particules** (`equations/
  particles.py`) sont des boucles Python sur les pas (correctes mais limitées à
  quelques centaines de milliers de points par couche) — candidates n°1 au GPU.
  L'interface `Equation.sample` est conçue pour ne pas changer lors de ce portage.
  Traité en Phase 5.
- Le contrôle de viabilité peut laisser passer des formes quasi 1D ; un critère
  de « surface minimale » plus fin est envisageable. Traité en Phase 5 (viabilité
  affinée).
