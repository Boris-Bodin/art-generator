# Feuille de route

La Phase 1 pose des fondations propres et un moteur qui produit déjà des œuvres.
Les phases suivantes enrichissent le langage artistique sans casser l'interface
(génome sérialisable, registre d'équations, modèle « nuage de points »).

## MVP



### Phase 1 — Fondations ✅ (livré)

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

### Phase 2 — Richesse du langage ✅ (livré)

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

### Phase 2+ — Compléments ✅ (livré)

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

### Phase 3 — Système de particules ✅ (livré)

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

### Phase 4 — Composition & fonds ✅ (livré)

Le rendu était un « light painting » **additif** : chaque couche valait noir là
où il n'y avait pas de forme, rendant le fond noir quasi obligatoire. Cette phase
**découple la forme du fond** (compositing par alpha) et élargit fonds et cadrage,
sans casser les invariants (seed→pixels identiques, round-trip JSON — le rendu
sur fond noir reste identique au pixel près). Tout nouveau paramètre passe par le
génome et est tiré par `generators/genome_generator.py`.

- [x] **4a — Compositing par alpha** : `render_layer` renvoie désormais
      `(color, alpha)`, la couverture `alpha` étant dérivée de la densité
      (`renderers/accumulation.py::_resolve`) ; l'engine compose via
      `core/blend.py::composite`, de sorte que les zones vides (`alpha = 0`)
      laissent transparaître le fond quel qu'il soit (fin du fond noir implicite).
      La couleur non prémultipliée garantit que `color·alpha` reproduit l'ancien
      tampon additif → fond noir inchangé.
- [x] **4b — Mode « encre sur papier » (soustractif)** : modèle de rendu `ink`
      (champ `LayerGenome.render_model`) où le pigment *absorbe* la lumière du
      support (`out = base·(1 - a·(1 - color))`) au lieu d'en ajouter ; les
      couches s'assombrissent en s'empilant, rendant des formes sombres lisibles
      sur papier clair. Le générateur produit ~25 % d'œuvres à l'encre, avec
      palettes de pigments sombres et fonds « papier ».
- [x] **4c — Fonds enrichis** (`core/background.py`) : dégradés **directionnels**
      (paramètre `angle`) et **radiaux** (`radial`), plus **vignette**
      optionnelle applicable à tout fond ; au-delà des `black`/`white`/`gradient`.
- [x] **4d — Cadrage par densité** (`utils/math_utils.py::fit_to_canvas`,
      paramètre `center_on`) : le mode `density` centre sur le **centroïde
      pondéré par la densité** et met à l'échelle sur un **rayon robuste**, pour
      cadrer sur le cœur de la forme (champ `LayerGenome.framing`).

### Phase 5 — Export ✅ (livré)

Cette phase élargit les débouchés du moteur sans toucher aux invariants : le
rendu par tuiles est **identique au pixel près** au chemin simple (testé), et
l'export vectoriel réutilise le même nuage de points projeté.

- [x] **Export vectoriel SVG/PDF** (`exporters/vector.py`) « par tracés » : chaque
      point du nuage projeté devient un disque coloré (stipple). Un *light
      painting* additif d'un million de points ne se transpose pas fidèlement en
      géométrie — l'export vectoriel est donc une **esthétique distincte**,
      redimensionnable à l'infini. Réalisé via **matplotlib** (déjà une
      dépendance) : un même code produit SVG *et* PDF, sans binaire natif (à la
      place de CairoSVG, fragile à installer). Sous-échantillonnage déterministe
      (plafond de points par couche) pour borner la taille du fichier.
- [x] **Résolutions HD/4K/8K/16K, ratio & DPI configurables** (`exporters/
      resolution.py`, options CLI `--preset`/`--ratio`/`--size`/`--dpi`) : le
      grand côté suit le préréglage, le rapport d'aspect façonne les deux
      dimensions. Un préréglage peut porter son **propre ratio** (format
      d'impression *displate* → 4000×5600) ; un `--ratio` explicite prime.
- [x] **Rendu indépendant de la résolution** (`core/engine.py::_scale`) : le
      nombre de points étant fixé dans le génome, monter en résolution diluait la
      densité par pixel et **faisait apparaître plus de fond**. Le rendu met
      désormais le nombre de points à l'échelle de l'**aire** (référence 1600 px,
      planché à 1×) pour garder une densité constante. Comme une aire 2D et un
      réseau de lignes 1D ne se comportent pas pareil, l'épaisseur et le glow ne
      sont mis à l'échelle **que pour les familles filamentaires** (vector_field,
      parametric, polar, complex — `accumulation._stroke_scale`), afin de
      préserver la densité du voile de lignes ; le poids est alors **normalisé
      par l'aire du disque** (`accumulation._point_modulation`) pour que le trait
      s'*élargisse sans s'alourdir* (densité visuelle constante). Les familles
      nuage (attractor, particles, fractal) gardent des traits fins et nets. Le **support 1D pur**
      (vector_field) fait croître ses points linéairement plutôt qu'avec l'aire
      (`accumulation._point_factor`). Enfin, les familles à **trajectoires
      intégrées** (vector_field, particles) préservent leur **durée intégrée**
      (`steps × dt`) en réduisant `dt` d'autant (`core/engine.py::_build_equation`)
      : sans cela, monter en résolution rallongerait les trajectoires et
      **changerait la forme** au lieu d'affiner l'échantillonnage. La borne de
      points du Buddhabrot (`equations/fractal.py`) a été relevée pour suivre
      l'aire. À 1600 px ou en deçà, le rendu est **inchangé au pixel près**.
- [x] **Rendu par tuiles** (`core/engine.py::_render_tiled`) : au-delà de 4096 px
      (ou sur `--tile`), l'image est composée **bande par bande** pour borner la
      mémoire (un tampon HDR 16K en float64 pèse plusieurs Go par couche). Chaque
      couche est projetée une fois (`renderers/accumulation.py::project_layer`),
      une pré-passe fige le percentile de normalisation **global** (`global_hi`)
      et les bandes sont élargies d'un halo pour un glow continu aux coutures —
      d'où l'identité pixel-à-pixel avec le chemin simple. Le fond est lui aussi
      calculé par bandes (`core/background.py`).

## V1

### Phase 1 — Interface & navigation ✅ (livré)

Cette phase donne un **atelier interactif** au moteur sans toucher aux invariants :
la logique (aperçu, navigation, presets) vit dans des modules **sans toolkit**,
donc testables sans écran ; la *vue* Tkinter ne fait que les câbler. Choix de
Tkinter (bibliothèque standard) pour rester fidèle au socle minimal du projet
(matplotlib/numpy/pillow) — **aucune dépendance nouvelle**.

- [x] **Interface graphique** (`ui/app.py`, commande `art-generator ui`) : trois
      colonnes — réglages globaux (seed, presets, fichier, fond) · aperçu · éditeur
      de couche. Édition en direct de tous les champs du génome (famille d'équation,
      fusion, médium light/ink, opacité, glow, exposition, épaisseur, symétrie,
      bruit, palette), changement de seed (précédent/suivant/aléatoire), et
      **sauvegarde/chargement** (JSON de génome, export image pleine résolution).
- [x] **Aperçu « temps réel »** (`ui/preview.py`, logique pure) : profite de
      l'indépendance à la résolution (rendu **fidèle** à petite taille, ≈ 560 px,
      cf. Phase 5) ; rendu **débouncé** et **hors thread principal** (Tk n'est pas
      thread-safe : résultat renvoyé par une file, sondée par `after`, stratégie
      « le dernier gagne »). Mode **brouillon** (`point_cap`) plafonnant les points
      pour un retour plus vif pendant l'édition ; l'export final garde le génome
      complet.
- [x] **Bibliothèque de presets** (`presets/library.py`) : catalogue **intégré**
      de seeds curées et nommées (une seed suffit — une œuvre = un génome) + presets
      **utilisateur** (génomes arbitraires édités à la main, enregistrés en JSON).
- [x] **Navigation dans l'espace des génomes** (`generators/navigation.py`) :
      `mutate` — un *petit pas* déterministe vers un voisin (perturbation douce des
      champs visuels, la **forme** `equation_params` restant intacte → viabilité
      préservée, jamais d'image noire) ; `reroll_equations` — un *saut* re-tirant
      des formes **viables** en gardant la mise en scène.

  Reste ouvert : rendu réellement temps réel (GPU, Phase 7) pour les familles
  coûteuses (attracteurs, particules).

### Phase 2 — UX

- [x] **Bibliothèque de presets** (`presets/library.py`) : replace the _BUILTIN seed 
      by the reading of the *.json file
- [x] **Desktop UI** : Indique if changement has been made on the seed
- [x] **Desktop UI** : You can select the famille d'une couche mais pas modifier les parametre
- [x] **Desktop UI** : add throbber in place of artwork when rendering  
- [x] **Desktop UI** : in the couche list Give better namming to better selection experience  
- [x] **Background** : I always see blacky gradient/radial, add more colorful background

### Phase 3 — Performance

- [x] **Vectorisation poussée** (bit-exact, pur NumPy → profite aussi au Web) :
      accumulation par `np.bincount` au lieu de `np.ufunc.at` (parcours préservé,
      chemin simple == rendu par tuiles au pixel près) et bruit de Perlin mémoïsé
      par seed + indexation directe du gradient. Gains : ~−24 % particules,
      ~−13 % attracteurs. Reste ouvert : **multiprocessing** (peu rentable sur un
      rendu simple, indisponible en WASM → fallback séquentiel obligatoire).
- [ ] **Accélération GPU (Numba/CUDA) — reportée (Phase 7).** La cible naturelle
      est la boucle **chaotique** des attracteurs : un écart d'1 ULP (`sin`/`cos`
      Numba ≠ NumPy) diverge totalement, et la Web tourne en Python pur (Pyodide,
      pas de Numba) → même seed ⇒ image différente desktop vs Web. Incompatible
      avec l'invariant « même rendu ». À rouvrir en Phase 7 avec la dette GPU.
- [ ] **Viabilité affinée** : critère de « surface minimale » plus fin pour
      rejeter les formes quasi 1D que le contrôle actuel laisse passer
      (`generators/quality.py`).

### Phase 4 - Stabilization

- [ ] **Desktop UI** : faire un vrai formulaire pour les paramètres d'équation (types,
  bornes, champs imbriqués) au lieu de l'éditeur JSON temporaire.
- [ ] Some **fractal** without symetry are wierd 
  - Nuage de point en cercle
  - Perte de densité sur 3 axes cardinal en dehors du carré concentric
- [ ] Create **seed** from json ?
- [ ] **The preset** saved need to be put in the presets package neer the built in one, 
  to be include in the next commit to be visible on the Web UI 
- [ ] **Desktop UI** select resolution/ratio, pouvoir export 
- [ ] **Web App** : better mobile responsive view
- [ ] **Web UI** : add test onb the web app, and not on the build script 

## V2

### Phase 1 — Animation

- [ ] Animation des paramètres, couleurs, particules, équations (keyframes)
- [ ] **Bruit 3D** (dimension temporelle) pour une animation cohérente des
      champs de bruit (laissé ouvert en Phase 2+)
- [ ] **Particules variables dans le temps** : taille et opacité par particule
      évoluant au fil de la vie (laissé ouvert en Phase 3)
- [ ] Export temporel : GIF, MP4, séquences PNG

## Dette technique connue

- [ ] L'itération des attracteurs **et l'advection des particules** (`equations/
  particles.py`) sont des boucles Python sur les pas (correctes mais limitées à
  quelques centaines de milliers de points par couche) — candidates n°1 au GPU.
  L'interface `Equation.sample` est conçue pour ne pas changer lors de ce portage.
  À traiter en Phase 7.
- [ ] Le contrôle de viabilité peut laisser passer des formes quasi 1D ; un critère
  de « surface minimale » plus fin est envisageable. À traiter en Phase 7
  (viabilité affinée).
