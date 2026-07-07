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

## Phase 2 — Richesse du langage

- [ ] **Bruit** : Perlin, Simplex, Worley + bruit personnalisé, appliqué aux
      coordonnées, couleurs, épaisseurs et à la lumière
- [ ] **Champs de vecteurs** : `dx/dt = f(x,y)`, `dy/dt = g(x,y)` avec advection
      de particules (nouvelle famille dans le registre)
- [ ] **Domaines complexes** : itérations et transformations sur `C`
- [ ] **Fractales** : Mandelbrot / Julia (architecture prête, non central)
- [ ] Palettes HSL/HSV, dégradés multi-arrêts, palettes procédurales avancées

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
