"""Interface graphique et navigation.

Le sous-module sépare la **logique** (calcul d'aperçu, indépendant de tout
toolkit — :mod:`art_generator.ui.preview`) de la **vue** Tkinter
(:mod:`art_generator.ui.app`, importée paresseusement pour ne pas exiger Tk là où
seule la logique sert).
"""
