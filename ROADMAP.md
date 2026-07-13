# Feuille de route

Le MVP, la V1 et la Phase 1 de la V2 (animation) sont **livrés** : moteur
reproductible, familles d'équations, particules, compositing, export
PNG/TIFF/SVG/PDF, résolutions HD→16K, UI desktop, Web App et animation.
Ce document ne conserve que les **chantiers ouverts** et les **pistes** pour la
suite. L'historique détaillé des phases livrées est dans l'historique Git.

Tout enrichissement doit préserver les invariants du moteur (voir `CLAUDE.md`) :
génome sérialisable, une seed → un génome → des pixels identiques, round-trip
JSON, modèle « nuage de points » et registre comme seul point d'extension.

## Chantiers ouverts

### Performance — Accélération GPU (reportée)

La cible naturelle est la boucle **chaotique** des attracteurs et l'advection des
particules (`equations/particles.py`), aujourd'hui des boucles Python (correctes
mais bornées à quelques centaines de milliers de points par couche). Blocage :
un écart d'1 ULP (`sin`/`cos` Numba ≠ NumPy) diverge totalement sur les systèmes
chaotiques, et la Web tourne en Python pur (Pyodide, pas de Numba) → même seed ⇒
image différente desktop vs Web. **Incompatible avec l'invariant « même rendu »**
tant qu'un chemin bit-exact partagé n'est pas trouvé. `Equation.sample` est
conçue pour ne pas changer lors de ce portage.

### Viabilité affinée (dette)

Le contrôle de viabilité (`generators/quality.py`) peut encore laisser passer des
formes **quasi-1D** ; un critère de « surface minimale » plus fin que la dimension
de box-counting actuelle est envisageable.

### Animation — compléments

- **Taille/opacité par particule au fil de la vie** : nécessiterait d'étendre le
  contrat `sample(n) -> (points, values)` par un canal de poids.
- **Éditeur de timeline par image-clé** : l'UI propose des effets prédéfinis, pas
  l'édition de pistes arbitraires (`Track`/`Keyframe` existent déjà côté moteur).

## Amélioration

### Phase 1 Langage artistique

- **Nouvelles familles d'équations** (via le registre, sans toucher au moteur) :
  L-systèmes / courbes de remplissage (Hilbert, Peano), diagrammes de Voronoi
  stipplés, agrégation par diffusion limitée (DLA), automates cellulaires
  continus (Lenia), champs de réaction-diffusion (Gray-Scott).
- **Dégradés le long de la trajectoire** : mapper la couleur sur la longueur d'arc
  cumulée plutôt que sur `values`, pour des rubans à progression chromatique.
- **Textures de trait** : noyau d'accumulation non circulaire (anisotrope, orienté
  par le champ de vitesse) pour un rendu « coup de pinceau ».

### Phase 2 Direction artistique & découverte

- **Recherche par similarité / exploration guidée** : vecteur d'empreinte visuelle
  (histogramme de couleurs + occupation) par génome, pour naviguer vers des
  voisins « qui ressemblent » plutôt que par mutation aveugle.
- **Curation par lot** : noter une planche-contact et rejouer les seeds retenues
  comme presets nommés.
- **Import de palette depuis une image** : extraire une palette harmonique d'une
  photo de référence et l'injecter dans le génome.

### Phase 4 Export & Interface

- **Historique & comparaison A/B** dans l'UI desktop (annuler/refaire sur le
  génome, vue côte à côte de deux seeds).
- **Galerie interactive** dans la Web App (grille de seeds curées, deep-link vers
  un génome).
- **Tuiles sans couture (seamless / wallpaper)** : domaine torique pour les
  familles à base de bruit, afin de produire des motifs répétables.
- **Sortie multi-format en un passage** (PNG + SVG + génome JSON + vignette) pour
  publication.
