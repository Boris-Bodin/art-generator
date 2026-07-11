"""Interface graphique Tkinter — la *vue*.

Trois colonnes : réglages globaux (seed, presets, fichier, fond) à gauche, aperçu
temps réel au centre, éditeur de couche à droite. Toute la logique lourde est
déléguée aux modules testables (:mod:`ui.preview`, :mod:`generators.navigation`,
:mod:`presets.library`, :mod:`exporters.genome_io`) ; ce fichier ne fait que
câbler des widgets sur les champs du génome et orchestrer un rendu d'aperçu
**débouncé** et **hors thread principal** pour garder l'UI fluide.

Le rendu d'aperçu tourne dans un thread de travail : Tk n'étant pas thread-safe,
le résultat est renvoyé au thread principal via une file, sondée par ``after``.
Un identifiant de requête monotone garantit que seul le *dernier* rendu demandé
met à jour le canevas (stratégie « le dernier gagne »).
"""

from __future__ import annotations

import copy
import json
import queue
import random
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from ..core.genome import ArtworkGenome, LayerGenome
from ..equations import registry
from ..exporters import genome_io, image as image_export, resolution
from ..generators import navigation
from ..generators.genome_generator import generate
from ..palettes import procedural
from ..presets import library
from ..core import animation as animation_core
from . import anim_options, param_form, preview

_BACKGROUNDS = ["black", "white", "gradient", "radial"]
_BLEND_MODES = ["normal", "add", "screen", "multiply", "difference"]
_RENDER_MODELS = ["light", "ink"]
_COLOR_BY = ["velocity", "t", "radius"]
_FRAMINGS = ["box", "density"]
_SYMMETRIES = ["none", "mirror", "radial", "kaleidoscope"]
_NOISE_TYPES = ["none", "perlin", "simplex", "fbm", "worley"]
# Préréglages de sortie proposés dans l'UI : clés de exporters.resolution.PRESETS
# (sans les alias) → libellés lisibles. Displate porte son propre ratio (1:1.4).
_RES_KEYS = ["preview", "hd", "fhd", "2k", "4k", "8k", "16k", "displate"]
_RES_LABELS = {
    "preview": "Aperçu 1600",
    "hd": "HD 720",
    "fhd": "Full HD 1080",
    "2k": "QHD 2K",
    "4k": "UHD 4K",
    "8k": "8K",
    "16k": "16K",
    "displate": "Displate",
}
# « auto » = laisser le préréglage imposer son ratio (carré si aucun).
_RATIOS = ["auto", "1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "1:1.4"]

_RES_LABEL_LIST = [_RES_LABELS[k] for k in _RES_KEYS]
_RES_LABEL_TO_KEY = {_RES_LABELS[k]: k for k in _RES_KEYS}
_RES_KEY_FOR_EDGE = {resolution.PRESETS[k].long_edge: k for k in _RES_KEYS}

_DEBOUNCE_MS = 300
_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def _layer_detail(layer: LayerGenome) -> str:
    params = layer.equation_params
    if params.get("variant"):
        return str(params["variant"])
    if params.get("kind"):
        return str(params["kind"])
    if layer.equation_family == "particles":
        emitter = params.get("emitter", {})
        if isinstance(emitter, dict):
            return f"emitter {emitter.get('type', 'disk')}"
    if layer.equation_family == "vector_field":
        return f"flow seed {params.get('seed', '?')}"
    if layer.equation_family == "parametric":
        return f"{params.get('a', '?')}:{params.get('c', '?')}:{params.get('f', '?')}"
    if layer.equation_family == "polar":
        return f"k {params.get('k1', '?')}/{params.get('k2', '?')}"
    if layer.equation_family == "complex":
        return f"map seed {params.get('seed', '?')}"
    if layer.equation_family == "fractal":
        return str(params.get("mode", "orbit"))
    return "forme"


def _layer_label(layer: LayerGenome, index: int, total: int) -> str:
    """Libellé compact et informatif pour la liste des couches."""
    detail = _layer_detail(layer)
    symmetry = ""
    if layer.symmetry != "none":
        symmetry = f" · {layer.symmetry} x{layer.symmetry_order}"
    return f"{index + 1}. {layer.equation_family} · {detail}{symmetry} ({index + 1}/{total})"


class ArtGeneratorApp(tk.Tk):
    """Fenêtre principale de l'éditeur d'œuvres."""

    def __init__(self, seed: int | None = None) -> None:
        super().__init__()
        self.title("Art Generator — éditeur")
        self.geometry("1180x720")
        self.minsize(1000, 640)

        seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self.genome: ArtworkGenome = generate(seed)
        self._nav_seed = seed  # sert de graine évolutive pour la navigation
        self._current_layer = 0
        self._dirty = False

        self._loading = False          # supprime les callbacks pendant un remplissage programmatique
        self._editor_widgets: list = []  # widgets de l'éditeur de couche (désactivés si aucune couche)
        self._render_job: str | None = None
        self._request_id = 0
        self._spinner_job: str | None = None
        self._spinner_index = 0
        self._result_q: queue.Queue = queue.Queue()
        self._photo: ImageTk.PhotoImage | None = None

        # -- état de l'aperçu animé (lecture d'une boucle dans le canevas) --
        self._anim_q: queue.Queue = queue.Queue()
        self._anim_playing = False
        self._anim_frames: list[Image.Image] | None = None
        self._anim_index = 0
        self._anim_play_job: str | None = None
        self._anim_fps = 24
        self._anim_exporting = False

        # -- état pan & zoom de l'aperçu --
        self._preview_image = None          # dernière image d'aperçu (PIL)
        self._view_zoom = 1.0               # 1.0 = ajusté au canevas
        self._view_offset: tuple[float, float] | None = None  # coin haut-gauche (px canevas)
        self._pan_anchor: tuple[float, float, float, float] | None = None

        self._build_ui()
        self._update_title()
        self._refresh_all()
        self.after(50, self._poll_results)
        self.after(60, self._poll_anim)
        self._schedule_render()

    # -- construction de l'interface -----------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    def _labelled_scale(self, parent, label, lo, hi, command, register=False):
        """Ligne étiquette + curseur ; renvoie la ``DoubleVar`` liée.

        ``register`` inscrit le curseur dans :attr:`_editor_widgets` afin qu'il
        soit désactivé quand l'œuvre ne contient aucune couche.
        """
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.DoubleVar()
        scale = ttk.Scale(row, from_=lo, to=hi, variable=var,
                          command=lambda _v: command(var.get()))
        scale.pack(side="left", fill="x", expand=True)
        if register:
            self._editor_widgets.append(scale)
        return var

    def _labelled_combo(self, parent, label, values, command, register=False):
        """Ligne étiquette + combobox ; renvoie la ``StringVar`` liée.

        ``register`` inscrit la combobox dans :attr:`_editor_widgets` afin qu'elle
        soit désactivée quand l'œuvre ne contient aucune couche.
        """
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)
        combo.bind("<<ComboboxSelected>>", lambda _e: command(var.get()))
        if register:
            self._editor_widgets.append(combo)
        return var

    def _format_combo(self, parent, label, values, command):
        """Ligne étiquette + combobox de format ; ``command`` s'exécute à la sélection.

        Renvoie ``(StringVar, Combobox)`` : la combobox est conservée pour lui
        ajouter, au besoin, la valeur courante du génome quand elle sort de la
        liste standard.
        """
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)
        combo.bind("<<ComboboxSelected>>", lambda _e: command())
        return var, combo

    def _build_left_panel(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=0, sticky="ns")

        ttk.Label(panel, text="Œuvre", font=("", 11, "bold")).pack(anchor="w")

        seed_row = ttk.Frame(panel)
        seed_row.pack(fill="x", pady=4)
        ttk.Label(seed_row, text="Seed", width=6).pack(side="left")
        self._seed_var = tk.StringVar()
        entry = ttk.Entry(seed_row, textvariable=self._seed_var, width=12)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self._apply_seed())
        self._dirty_badge = tk.Label(
            seed_row,
            text="Modifié",
            bg="#b45309",
            fg="white",
            padx=6,
            pady=1,
            font=("", 8, "bold"),
        )
        self._seed_prev_btn = ttk.Button(seed_row, text="◀", width=3, command=lambda: self._step_seed(-1))
        self._seed_prev_btn.pack(side="left")
        ttk.Button(seed_row, text="▶", width=3, command=lambda: self._step_seed(1)).pack(side="left")

        ttk.Button(panel, text="Seed aléatoire", command=self._random_seed).pack(fill="x", pady=2)
        ttk.Button(panel, text="Nouveau (vierge)", command=self._new_blank).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Naviguer", font=("", 10, "bold")).pack(anchor="w")
        ttk.Button(panel, text="Muter (voisin)", command=self._mutate).pack(fill="x", pady=2)
        ttk.Button(panel, text="Re-tirer les formes", command=self._reroll).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Presets", font=("", 10, "bold")).pack(anchor="w")
        preset_names = library.names()
        self._preset_var = tk.StringVar(value=preset_names[0] if preset_names else "")
        self._preset_combo = ttk.Combobox(
            panel, textvariable=self._preset_var, values=preset_names, state="readonly"
        )
        self._preset_combo.pack(fill="x", pady=2)
        ttk.Button(panel, text="Charger le preset", command=self._load_preset).pack(fill="x", pady=2)
        ttk.Button(panel, text="Enregistrer comme preset…", command=self._save_user_preset).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Fichier", font=("", 10, "bold")).pack(anchor="w")
        ttk.Button(panel, text="Ouvrir JSON…", command=self._open_json).pack(fill="x", pady=2)
        ttk.Button(panel, text="Enregistrer JSON…", command=self._save_json).pack(fill="x", pady=2)
        ttk.Button(panel, text="Exporter l'image…", command=self._export_image).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Format", font=("", 10, "bold")).pack(anchor="w")
        self._resolution_var, self._resolution_combo = self._format_combo(
            panel, "Résolution", _RES_LABEL_LIST, self._on_resolution_preset
        )
        self._ratio_var, self._ratio_combo = self._format_combo(
            panel, "Ratio", _RATIOS, self._apply_format
        )

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Fond", font=("", 10, "bold")).pack(anchor="w")
        self._bg_var = self._labelled_combo(panel, "Type", _BACKGROUNDS, self._on_background)
        self._vignette_var = self._labelled_scale(panel, "Vignette", 0.0, 0.6, self._on_vignette)

        self._build_animation_section(panel)

    def _build_animation_section(self, panel) -> None:
        """Section Animation : effets cochables, aperçu animé, export vidéo."""
        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Animation", font=("", 10, "bold")).pack(anchor="w")

        timing = ttk.Frame(panel)
        timing.pack(fill="x", pady=2)
        ttk.Label(timing, text="Frames", width=6).pack(side="left")
        self._anim_frames_var = tk.StringVar(value="90")
        ttk.Entry(timing, textvariable=self._anim_frames_var, width=5).pack(side="left")
        ttk.Label(timing, text="  fps", width=4).pack(side="left")
        self._anim_fps_var = tk.StringVar(value="24")
        ttk.Entry(timing, textvariable=self._anim_fps_var, width=5).pack(side="left")

        self._anim_color_var = tk.BooleanVar(value=True)
        self._anim_bg_var = tk.BooleanVar(value=True)
        self._anim_reveal_var = tk.BooleanVar(value=False)
        self._anim_noise_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(panel, text="Cycle de couleur", variable=self._anim_color_var).pack(anchor="w")
        ttk.Checkbutton(panel, text="Rotation du fond", variable=self._anim_bg_var).pack(anchor="w")
        ttk.Checkbutton(panel, text="Particules (comète)", variable=self._anim_reveal_var).pack(anchor="w")
        ttk.Checkbutton(panel, text="Flux de bruit", variable=self._anim_noise_var).pack(anchor="w")

        controls = ttk.Frame(panel)
        controls.pack(fill="x", pady=2)
        self._anim_play_btn = ttk.Button(controls, text="▶ Aperçu", command=self._toggle_anim_preview)
        self._anim_play_btn.pack(side="left", fill="x", expand=True)
        self._anim_export_btn = ttk.Button(controls, text="Exporter…", command=self._export_animation)
        self._anim_export_btn.pack(side="left", fill="x", expand=True)

    def _build_center_panel(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(panel, background="#111111", highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", lambda _e: self._draw_preview())
        self._canvas.bind("<MouseWheel>", self._on_wheel)          # Windows / macOS
        self._canvas.bind("<Button-4>", lambda e: self._on_wheel(e, 120))   # Linux molette +
        self._canvas.bind("<Button-5>", lambda e: self._on_wheel(e, -120))  # Linux molette -
        self._canvas.bind("<Button-1>", self._on_pan_start)
        self._canvas.bind("<B1-Motion>", self._on_pan_move)
        self._canvas.bind("<Double-Button-1>", lambda _e: self._reset_view())
        self._status = ttk.Label(panel, text="Molette : zoom · glisser : déplacer · double-clic : ajuster")
        self._status.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _build_right_panel(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=2, sticky="ns")

        ttk.Label(panel, text="Couche", font=("", 11, "bold")).pack(anchor="w")
        self._layer_var = tk.StringVar()
        self._layer_combo = ttk.Combobox(panel, textvariable=self._layer_var, state="readonly")
        self._layer_combo.pack(fill="x", pady=2)
        self._layer_combo.bind("<<ComboboxSelected>>", lambda _e: self._select_layer())

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=2)
        ttk.Button(buttons, text="＋ Ajouter", command=self._add_layer).pack(side="left", fill="x", expand=True)
        self._delete_btn = ttk.Button(buttons, text="－ Supprimer", command=self._delete_layer)
        self._delete_btn.pack(side="left", fill="x", expand=True)

        self._family_var = self._labelled_combo(panel, "Famille", registry.families(), self._on_family, register=True)
        self._palette_btn = ttk.Button(panel, text="Palette aléatoire", command=self._random_palette)
        self._palette_btn.pack(fill="x", pady=2)
        self._editor_widgets.append(self._palette_btn)
        self._params_btn = ttk.Button(panel, text="Paramètres équation…", command=self._edit_params)
        self._params_btn.pack(fill="x", pady=2)
        self._editor_widgets.append(self._params_btn)

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._blend_var = self._labelled_combo(panel, "Fusion", _BLEND_MODES, lambda v: self._set_layer("blend_mode", v), register=True)
        self._model_var = self._labelled_combo(panel, "Médium", _RENDER_MODELS, lambda v: self._set_layer("render_model", v), register=True)
        self._colorby_var = self._labelled_combo(panel, "Couleur par", _COLOR_BY, lambda v: self._set_layer("color_by", v), register=True)
        self._framing_var = self._labelled_combo(panel, "Cadrage", _FRAMINGS, lambda v: self._set_layer("framing", v), register=True)

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._opacity_var = self._labelled_scale(panel, "Opacité", 0.0, 1.0, lambda v: self._set_layer("opacity", v), register=True)
        self._glow_var = self._labelled_scale(panel, "Glow", 0.0, 1.0, lambda v: self._set_layer("glow", v), register=True)
        self._exposure_var = self._labelled_scale(panel, "Exposition", 0.4, 2.5, lambda v: self._set_layer("exposure", v), register=True)
        self._thickness_var = self._labelled_scale(panel, "Épaisseur", 1.0, 4.0, lambda v: self._set_layer("thickness", v), register=True)

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._symmetry_var = self._labelled_combo(panel, "Symétrie", _SYMMETRIES, lambda v: self._set_layer("symmetry", v), register=True)
        self._order_var = self._labelled_scale(panel, "Ordre", 2, 12, lambda v: self._set_layer("symmetry_order", int(round(v))), register=True)

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._noise_var = self._labelled_combo(panel, "Bruit", _NOISE_TYPES, lambda v: self._set_layer("noise_type", v), register=True)
        self._warp_var = self._labelled_scale(panel, "Warp", 0.0, 0.6, lambda v: self._set_layer("warp", v), register=True)
        self._cnoise_var = self._labelled_scale(panel, "Bruit coul.", 0.0, 0.6, lambda v: self._set_layer("color_noise", v), register=True)
        self._lnoise_var = self._labelled_scale(panel, "Bruit lum.", 0.0, 1.0, lambda v: self._set_layer("light_noise", v), register=True)

    # -- synchronisation widgets <-> génome ----------------------------------

    @property
    def _layer(self):
        return self.genome.layers[self._current_layer]

    def _refresh_all(self) -> None:
        """Recharge tous les widgets depuis le génome (sans déclencher de callback)."""
        self._loading = True
        try:
            self._seed_var.set(str(self.genome.seed))
            self._sync_format()
            self._bg_var.set(self.genome.background)
            self._vignette_var.set(float(self.genome.background_params.get("vignette", 0.0)))
            n = len(self.genome.layers)
            self._layer_combo["values"] = [
                _layer_label(layer, i, n) for i, layer in enumerate(self.genome.layers)
            ]
            if n == 0:
                self._current_layer = 0
                self._layer_var.set("(aucune couche)")
                self._set_editor_enabled(False)
                self._delete_btn.state(["disabled"])
                return
            self._current_layer = min(self._current_layer, n - 1)
            self._layer_var.set(_layer_label(self._layer, self._current_layer, n))
            self._set_editor_enabled(True)
            self._delete_btn.state(["!disabled"])  # supprimer jusqu'à 0 couche est permis
            self._refresh_layer()
        finally:
            self._loading = False

    def _sync_format(self) -> None:
        """Reflète les dimensions du génome dans les combos résolution/ratio.

        Une valeur hors de la liste standard (preset au format inhabituel) est
        ajoutée à la volée pour rester affichable et sélectionnable.
        """
        w, h = self.genome.width, self.genome.height
        key = _RES_KEY_FOR_EDGE.get(max(w, h))
        label = _RES_LABELS[key] if key else str(max(w, h))
        self._fill_combo(self._resolution_combo, self._resolution_var, label, _RES_LABEL_LIST)
        ratio = resolution.simplify_ratio(w, h)
        self._fill_combo(self._ratio_combo, self._ratio_var, ratio, _RATIOS)

    @staticmethod
    def _fill_combo(combo, var, value: str, base: list[str]) -> None:
        values = base if value in base else [*base, value]
        combo["values"] = values
        var.set(value)

    def _on_resolution_preset(self) -> None:
        """Sélection d'un préréglage : s'il porte son propre ratio, le refléter.

        Ainsi choisir « Displate » bascule le combo Ratio sur ``1:1.4`` ; changer
        ensuite le Ratio prime (handler distinct, non écrasé). Les préréglages sans
        ratio propre laissent le Ratio courant inchangé.
        """
        key = _RES_LABEL_TO_KEY.get(self._resolution_var.get())
        if key is not None:
            preset_ratio = resolution.PRESETS[key].ratio
            if preset_ratio is not None:
                self._fill_combo(self._ratio_combo, self._ratio_var, preset_ratio, _RATIOS)
        self._apply_format()

    def _apply_format(self) -> None:
        if self._loading:
            return
        label = self._resolution_var.get()
        key = _RES_LABEL_TO_KEY.get(label)
        ratio = self._ratio_var.get()
        ratio = None if ratio == "auto" else ratio
        try:
            if key is not None:
                w, h = resolution.resolve_dimensions(preset=key, ratio=ratio)
            else:  # valeur personnalisée : grand côté numérique
                w, h = resolution.resolve_dimensions(size=int(label), ratio=ratio)
        except (ValueError, TypeError):
            return
        self.genome.width, self.genome.height = w, h
        self._mark_dirty()
        self._schedule_render()

    def _set_editor_enabled(self, enabled: bool) -> None:
        """Active ou désactive les widgets d'édition de couche."""
        for widget in self._editor_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                widget.configure(state="normal" if enabled else "disabled")

    def _refresh_layer(self) -> None:
        layer = self._layer
        self._family_var.set(layer.equation_family)
        self._blend_var.set(layer.blend_mode)
        self._model_var.set(layer.render_model)
        self._colorby_var.set(layer.color_by)
        self._framing_var.set(layer.framing)
        self._opacity_var.set(layer.opacity)
        self._glow_var.set(layer.glow)
        self._exposure_var.set(layer.exposure)
        self._thickness_var.set(layer.thickness)
        self._symmetry_var.set(layer.symmetry)
        self._order_var.set(layer.symmetry_order)
        self._noise_var.set(layer.noise_type)
        self._warp_var.set(layer.warp)
        self._cnoise_var.set(layer.color_noise)
        self._lnoise_var.set(layer.light_noise)

    def _set_layer(self, field: str, value) -> None:
        if self._loading or not self.genome.layers:
            return
        setattr(self._layer, field, value)
        self._mark_dirty()
        self._schedule_render()

    def _select_layer(self) -> None:
        if not self.genome.layers:
            return
        label = self._layer_var.get()
        try:
            self._current_layer = int(label.split(".", 1)[0]) - 1
        except (IndexError, ValueError):
            self._current_layer = 0
        self._loading = True
        try:
            self._refresh_layer()
        finally:
            self._loading = False

    # -- actions gauche -------------------------------------------------------

    def _update_title(self) -> None:
        marker = " *" if self._dirty else ""
        self.title(f"Art Generator — éditeur{marker}")
        if hasattr(self, "_dirty_badge"):
            if self._dirty:
                self._dirty_badge.pack(side="left", padx=(6, 0), before=self._seed_prev_btn)
            else:
                self._dirty_badge.pack_forget()

    def _mark_dirty(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._update_title()

    def _refresh_presets(self, select: str | None = None) -> None:
        preset_names = library.names()
        self._preset_combo["values"] = preset_names
        if select in preset_names:
            self._preset_var.set(select)
        elif self._preset_var.get() not in preset_names:
            self._preset_var.set(preset_names[0] if preset_names else "")

    def _set_genome(self, genome: ArtworkGenome, dirty: bool = False) -> None:
        self.genome = genome
        self._dirty = dirty
        self._update_title()
        self._refresh_all()
        self._schedule_render()

    def _apply_seed(self) -> None:
        try:
            seed = int(self._seed_var.get())
        except ValueError:
            return
        self._nav_seed = seed
        self._set_genome(generate(seed))

    def _step_seed(self, delta: int) -> None:
        self._nav_seed = self.genome.seed + delta
        self._set_genome(generate(self._nav_seed))

    def _random_seed(self) -> None:
        self._nav_seed = random.randint(0, 2**31 - 1)
        self._set_genome(generate(self._nav_seed))

    def _new_blank(self) -> None:
        """Repart de zéro : canevas vide (fond noir, aucune couche)."""
        blank = ArtworkGenome(
            seed=self.genome.seed,
            width=self.genome.width,
            height=self.genome.height,
            background="black",
            background_params={"vignette": 0.0},
            layers=[],
            title="Œuvre vierge",
        )
        self._current_layer = 0
        self._set_genome(blank, dirty=True)

    def _mutate(self) -> None:
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._set_genome(navigation.mutate(self.genome, self._nav_seed), dirty=True)

    def _reroll(self) -> None:
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._set_genome(navigation.reroll_equations(self.genome, self._nav_seed), dirty=True)

    def _load_preset(self) -> None:
        if self._preset_var.get():
            genome = library.load(self._preset_var.get())
            self._nav_seed = genome.seed  # la navigation repart de la seed du preset
            self._set_genome(genome)

    def _save_user_preset(self) -> None:
        name = simpledialog.askstring("Preset", "Nom du preset :", parent=self)
        if not name:
            return
        in_package = messagebox.askyesno(
            "Preset",
            "Enregistrer dans le package (versionné, livré au prochain commit et "
            "visible sur la Web UI) ?\n\nNon = preset personnel local.",
            parent=self,
        )
        save = library.save_builtin_preset if in_package else library.save_user_preset
        path = save(self.genome, name)
        self._dirty = False
        self._update_title()
        self._refresh_presets(select=name)
        messagebox.showinfo("Preset", f"Enregistré :\n{path}")

    def _open_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Génome JSON", "*.json")])
        if not path:
            return
        try:
            genome = genome_io.load(path)
        except Exception as exc:  # pragma: no cover - dépend du fichier choisi
            messagebox.showerror("Ouverture", str(exc))
            return
        self._nav_seed = genome.seed  # la navigation repart de la seed du fichier
        self._set_genome(genome)

    def _save_json(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Génome JSON", "*.json")])
        if path:
            genome_io.save(self.genome, path)
            self._dirty = False
            self._update_title()

    def _export_image(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png"), ("TIFF", "*.tiff"),
                                                       ("JPEG", "*.jpg")])
        if not path:
            return
        self._status.configure(text="Rendu pleine résolution…")
        self.update_idletasks()
        img = preview.Engine().render(self.genome)
        image_export.save_image(img, Path(path))
        self._status.configure(text=f"Exporté : {path}")

    def _on_background(self, value: str) -> None:
        if self._loading:
            return
        self.genome.background = value
        self.genome.background_params = self._default_background_params(value)
        self._loading = True
        try:
            self._vignette_var.set(float(self.genome.background_params.get("vignette", 0.0)))
        finally:
            self._loading = False
        self._mark_dirty()
        self._schedule_render()

    def _default_background_params(self, kind: str) -> dict:
        """Paramètres de fond raisonnables selon le médium des couches."""
        vignette = float(self._vignette_var.get())
        ink = any(layer.render_model == "ink" for layer in self.genome.layers)
        if kind in ("black", "white"):
            return {"vignette": vignette}
        if ink:
            warm = (0.96, 0.95, 0.92)
            if kind == "gradient":
                return {"top": warm, "bottom": (0.85, 0.84, 0.8), "vignette": vignette}
            return {"inner": warm, "outer": (0.85, 0.84, 0.8), "radius": 0.9, "vignette": vignette}
        if kind == "gradient":
            return {"top": (0.10, 0.07, 0.18), "bottom": (0.02, 0.08, 0.11),
                    "angle": 35.0, "vignette": vignette}
        return {"inner": (0.12, 0.07, 0.19), "outer": (0.02, 0.08, 0.11),
                "radius": 0.85, "vignette": vignette}

    def _on_vignette(self, value: float) -> None:
        if self._loading:
            return
        params = dict(self.genome.background_params)
        params["vignette"] = float(value)
        self.genome.background_params = params
        self._mark_dirty()
        self._schedule_render()

    # -- actions droite -------------------------------------------------------

    def _on_family(self, family: str) -> None:
        if self._loading or not self.genome.layers:
            return
        from ..generators import quality
        from ..core.rng import RNG

        layer = self._layer
        layer.equation_family = family
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        layer.equation_params = quality.viable_params(family, RNG(self._nav_seed))
        self._mark_dirty()
        self._refresh_all()
        self._schedule_render()

    def _random_palette(self) -> None:
        if not self.genome.layers:
            return
        from ..core.rng import RNG

        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._layer.palette = procedural.random_palette(RNG(self._nav_seed))
        self._mark_dirty()
        self._schedule_render()

    def _edit_params(self) -> None:
        """Formulaire typé des paramètres d'équation (un champ par paramètre).

        Le type de chaque widget (case à cocher, liste de choix, saisie) est
        inféré par :mod:`ui.param_form` depuis la valeur courante ; les dicts
        imbriqués (émetteur de particules…) sont aplatis en chemins pointés.
        """
        if not self.genome.layers:
            return
        layer = self._layer
        fields = param_form.describe(layer.equation_params, layer.equation_family)

        editor = tk.Toplevel(self)
        editor.title("Paramètres équation")
        editor.transient(self)
        editor.geometry("460x520")
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(0, weight=1)

        # Zone défilante : les familles riches (particules) ont beaucoup de champs.
        canvas = tk.Canvas(editor, highlightthickness=0)
        scroll = ttk.Scrollbar(editor, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas, padding=8)
        form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        form.columnconfigure(1, weight=1)

        getters = []  # [(Field, callable -> valeur brute du widget)]
        for i, fld in enumerate(fields):
            ttk.Label(form, text=fld.label, width=16).grid(row=i, column=0, sticky="w", pady=3)
            if fld.kind == "bool":
                var = tk.BooleanVar(value=bool(fld.value))
                ttk.Checkbutton(form, variable=var).grid(row=i, column=1, sticky="w")
            elif fld.kind == "choice":
                var = tk.StringVar(value=str(fld.value))
                ttk.Combobox(form, textvariable=var, values=list(fld.choices),
                             state="readonly").grid(row=i, column=1, sticky="ew")
            else:
                text = json.dumps(fld.value, ensure_ascii=False) if fld.kind == "json" else str(fld.value)
                var = tk.StringVar(value=text)
                ttk.Entry(form, textvariable=var).grid(row=i, column=1, sticky="ew")
            getters.append((fld, var.get))

        if not fields:
            ttk.Label(form, text="Aucun paramètre pour cette équation.").grid(row=0, column=0)

        buttons = ttk.Frame(editor, padding=(8, 0, 8, 8))
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew")

        def apply() -> None:
            updates = []
            for fld, get in getters:
                try:
                    updates.append((fld.path, param_form.coerce(fld.kind, get())))
                except Exception as exc:
                    messagebox.showerror(
                        "Paramètres équation",
                        f"Champ « {fld.label} » invalide : {exc}",
                        parent=editor,
                    )
                    return
            layer.equation_params = param_form.assemble(layer.equation_params, updates)
            self._mark_dirty()
            self._refresh_all()
            self._schedule_render()
            editor.destroy()

        ttk.Button(buttons, text="Appliquer", command=apply).pack(side="right")
        ttk.Button(buttons, text="Annuler", command=editor.destroy).pack(side="right", padx=(0, 6))

    # -- gestion des couches --------------------------------------------------

    def _make_layer(self) -> LayerGenome:
        """Fabrique une nouvelle couche viable, prête à être empilée.

        La forme est garantie non dégénérée par :mod:`generators.quality` et le
        tirage est piloté par ``_nav_seed`` (reproductible, avancé à chaque appel).
        """
        from ..generators import quality
        from ..core.rng import RNG

        self._nav_seed = (self._nav_seed + 1) % (2**31)
        rng = RNG(self._nav_seed)
        family = rng.choice(registry.families())
        return LayerGenome(
            equation_family=family,
            equation_params=quality.viable_params(family, rng),
            palette=procedural.random_palette(rng),
            color_by="velocity" if family == "attractor" else "t",
            blend_mode="add",
            opacity=1.0,
        )

    def _add_layer(self) -> None:
        """Ajoute une couche et la sélectionne."""
        self.genome.layers.append(self._make_layer())
        self._current_layer = len(self.genome.layers) - 1
        self._mark_dirty()
        self._refresh_all()
        self._schedule_render()

    def _delete_layer(self) -> None:
        """Supprime la couche courante (jusqu'à un canevas vide)."""
        if not self.genome.layers:
            return
        del self.genome.layers[self._current_layer]
        self._current_layer = max(0, self._current_layer - 1)
        self._mark_dirty()
        self._refresh_all()
        self._schedule_render()

    # -- animation ------------------------------------------------------------

    def _anim_options_from_ui(self) -> anim_options.AnimationOptions:
        """Lit les réglages d'animation de l'UI (valeurs invalides → défauts)."""
        def _int(var, default):
            try:
                return max(1, int(str(var.get()).strip()))
            except (ValueError, AttributeError):
                return default

        return anim_options.AnimationOptions(
            frames=_int(self._anim_frames_var, 90),
            fps=_int(self._anim_fps_var, 24),
            color_cycle=self._anim_color_var.get(),
            background_spin=self._anim_bg_var.get(),
            particle_reveal=self._anim_reveal_var.get(),
            noise_flow=self._anim_noise_var.get(),
        )

    def _toggle_anim_preview(self) -> None:
        if self._anim_playing or self._anim_frames is not None:
            self._halt_anim_preview()
            self._schedule_render()  # revient à l'aperçu statique
            return
        options = self._anim_options_from_ui()
        animated = anim_options.apply(self.genome, options)
        if animated.animation is None:
            self._status.configure(text="Animation : cocher au moins un effet.")
            return
        # Aperçu léger : plafonne le nombre de frames et rend en brouillon.
        n = min(animated.animation.frames, 36)
        times = [animation_core.frame_time(animated.animation, i) for i in range(n)]
        self._anim_fps = options.fps
        self._anim_play_btn.configure(text="⏹ Stop")
        self._status.configure(text=f"Aperçu animé : rendu de {n} frames…")
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        self._stop_spinner()
        self._request_id += 1  # invalide tout rendu statique en vol (ne pas écraser)

        def work() -> None:
            try:
                frames = []
                for k, t in enumerate(times, start=1):
                    static = animation_core.evaluate(animated, t)
                    frames.append(preview.render_preview(static, point_cap=preview.DRAFT_POINT_CAP))
                    self._anim_q.put(("progress", k, len(times)))
                self._anim_q.put(("ready", frames))
            except Exception as exc:  # pragma: no cover - robustesse UI
                self._anim_q.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    def _start_anim_playback(self, frames: list[Image.Image]) -> None:
        if not frames:
            return
        self._anim_frames = frames
        self._anim_index = 0
        self._anim_playing = True
        self._advance_anim()

    def _advance_anim(self) -> None:
        if not self._anim_playing or not self._anim_frames:
            return
        self._preview_image = self._anim_frames[self._anim_index]
        self._draw_preview()
        self._anim_index = (self._anim_index + 1) % len(self._anim_frames)
        delay = max(20, round(1000 / max(1, self._anim_fps)))
        self._anim_play_job = self.after(delay, self._advance_anim)

    def _halt_anim_preview(self) -> None:
        """Arrête la lecture de l'aperçu animé (sans reprogrammer de rendu)."""
        if self._anim_play_job is not None:
            self.after_cancel(self._anim_play_job)
            self._anim_play_job = None
        self._anim_playing = False
        self._anim_frames = None
        if hasattr(self, "_anim_play_btn"):
            self._anim_play_btn.configure(text="▶ Aperçu")

    def _export_animation(self) -> None:
        if self._anim_exporting:
            return
        options = self._anim_options_from_ui()
        animated = anim_options.apply(self.genome, options)
        if animated.animation is None:
            messagebox.showinfo("Animation", "Cocher au moins un effet à animer.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("GIF animé", "*.gif"), ("Vidéo MP4", "*.mp4"),
                       ("Séquence PNG (dossier)", "*")],
        )
        if not path:
            return
        self._halt_anim_preview()
        self._anim_exporting = True
        self._anim_export_btn.state(["disabled"])
        self._status.configure(text="Export de l'animation…")

        def report(done: int, total: int) -> None:
            self._anim_q.put(("export_progress", done, total))

        def work() -> None:
            from ..exporters import animation as animation_export
            try:
                out = animation_export.save_animation(animated, path, jobs=1, progress=report)
                self._anim_q.put(("export_done", out))
            except Exception as exc:  # pragma: no cover - dépend de l'environnement
                self._anim_q.put(("export_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def _poll_anim(self) -> None:
        """Draine la file de l'animation (aperçu + export) sur le thread principal."""
        try:
            while True:
                kind, *rest = self._anim_q.get_nowait()
                if kind == "progress":
                    done, total = rest
                    self._status.configure(text=f"Aperçu animé : rendu {done}/{total}…")
                elif kind == "ready":
                    self._start_anim_playback(rest[0])
                    self._status.configure(text="Aperçu animé (boucle). ▶/⏹ pour arrêter.")
                elif kind == "error":
                    self._halt_anim_preview()
                    self._status.configure(text=f"Aperçu animé — erreur : {rest[0]}")
                elif kind == "export_progress":
                    done, total = rest
                    self._status.configure(text=f"Export animation : {done}/{total} frames…")
                elif kind == "export_done":
                    self._anim_exporting = False
                    self._anim_export_btn.state(["!disabled"])
                    self._status.configure(text=f"Animation exportée : {rest[0]}")
                elif kind == "export_error":
                    self._anim_exporting = False
                    self._anim_export_btn.state(["!disabled"])
                    self._status.configure(text=f"Export animation — erreur : {rest[0]}")
        except queue.Empty:
            pass
        self.after(60, self._poll_anim)

    # -- rendu d'aperçu (débouncé, hors thread principal) --------------------

    def _schedule_render(self) -> None:
        self._halt_anim_preview()  # une édition reprend l'aperçu statique
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self._render_job = self.after(_DEBOUNCE_MS, self._start_render)

    def _start_render(self) -> None:
        self._render_job = None
        self._request_id += 1
        request_id = self._request_id
        snapshot = copy.deepcopy(self.genome)  # fige l'état pour le thread de travail
        self._status.configure(text="Rendu…")
        self._start_spinner(request_id)
        self._photo = None

        def work() -> None:
            start = time.perf_counter()
            try:
                img = preview.render_preview(snapshot, point_cap=preview.DRAFT_POINT_CAP)
                elapsed = time.perf_counter() - start
                self._result_q.put((request_id, img, elapsed, None))
            except Exception as exc:  # pragma: no cover - robustesse UI
                self._result_q.put((request_id, None, 0.0, exc))

        threading.Thread(target=work, daemon=True).start()

    def _start_spinner(self, request_id: int) -> None:
        self._stop_spinner()
        self._spinner_index = 0
        self._animate_spinner(request_id)

    def _animate_spinner(self, request_id: int) -> None:
        if request_id != self._request_id:
            return
        frame = _SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)]
        self._spinner_index += 1
        self._canvas.delete("all")
        cw = max(1, self._canvas.winfo_width())
        ch = max(1, self._canvas.winfo_height())
        self._canvas.create_text(
            cw / 2, ch / 2, text=f"{frame} Rendu…", fill="#f8fafc", font=("", 16, "bold")
        )
        self._spinner_job = self.after(90, lambda: self._animate_spinner(request_id))

    def _stop_spinner(self) -> None:
        if self._spinner_job is not None:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None

    def _poll_results(self) -> None:
        try:
            while True:
                request_id, img, elapsed, exc = self._result_q.get_nowait()
                if request_id != self._request_id:
                    continue  # rendu périmé (le dernier gagne)
                self._stop_spinner()
                if exc is not None:
                    self._status.configure(text=f"Erreur : {exc}")
                    continue
                self._preview_image = img
                self._draw_preview()
                zoom = f" · zoom {self._view_zoom:.1f}x" if self._view_zoom > 1.0 else ""
                self._status.configure(
                    text=f"{self.genome.width}×{self.genome.height} · aperçu "
                    f"{img.width}×{img.height} · {elapsed:.2f}s{zoom}"
                )
        except queue.Empty:
            pass
        self.after(50, self._poll_results)

    # -- pan & zoom de l'aperçu ----------------------------------------------

    def _fit_scale(self) -> float:
        """Échelle qui ajuste l'image au canevas (ratio préservé)."""
        img = self._preview_image
        cw = max(1, self._canvas.winfo_width())
        ch = max(1, self._canvas.winfo_height())
        return min(cw / img.width, ch / img.height)

    def _current_offset(self) -> tuple[float, float]:
        """Coin haut-gauche courant de l'image (centré si aucun décalage explicite)."""
        if self._view_offset is not None:
            return self._view_offset
        scale = self._fit_scale() * self._view_zoom
        cw = max(1, self._canvas.winfo_width())
        ch = max(1, self._canvas.winfo_height())
        return ((cw - self._preview_image.width * scale) / 2,
                (ch - self._preview_image.height * scale) / 2)

    def _draw_preview(self) -> None:
        """Dessine l'aperçu au zoom/décalage courants (portion visible seulement)."""
        img = self._preview_image
        if img is None:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        scale = self._fit_scale() * self._view_zoom
        ox, oy = self._current_offset()
        x0, y0, x1, y1 = preview.visible_source_box(img.width, img.height, cw, ch, scale, (ox, oy))
        self._canvas.delete("all")
        if x1 <= x0 or y1 <= y0:  # image hors champ (pan extrême)
            return
        crop = img.crop((x0, y0, x1, y1))
        dw = max(1, round((x1 - x0) * scale))
        dh = max(1, round((y1 - y0) * scale))
        self._photo = ImageTk.PhotoImage(crop.resize((dw, dh), Image.BILINEAR))
        self._canvas.create_image(ox + x0 * scale, oy + y0 * scale, anchor="nw", image=self._photo)

    def _on_wheel(self, event, delta: int | None = None) -> None:
        if self._preview_image is None:
            return
        step = event.delta if delta is None else delta
        self._apply_zoom(1.25 if step > 0 else 1 / 1.25, event.x, event.y)

    def _apply_zoom(self, factor: float, cx: float, cy: float) -> None:
        old = self._view_zoom
        new = min(8.0, max(1.0, old * factor))
        if new == old:
            return
        fit = self._fit_scale()
        ox, oy = self._current_offset()
        nox = preview.rescale_offset(ox, cx, fit * old, fit * new)
        noy = preview.rescale_offset(oy, cy, fit * old, fit * new)
        self._view_zoom = new
        self._view_offset = None if new <= 1.0001 else (nox, noy)
        self._draw_preview()

    def _on_pan_start(self, event) -> None:
        if self._preview_image is None or self._view_zoom <= 1.0:
            return
        ox, oy = self._current_offset()
        self._pan_anchor = (event.x, event.y, ox, oy)

    def _on_pan_move(self, event) -> None:
        if self._pan_anchor is None:
            return
        ax, ay, ox, oy = self._pan_anchor
        self._view_offset = (ox + (event.x - ax), oy + (event.y - ay))
        self._draw_preview()

    def _reset_view(self) -> None:
        """Réajuste l'aperçu au canevas (zoom 1, recentré)."""
        self._view_zoom = 1.0
        self._view_offset = None
        self._pan_anchor = None
        self._draw_preview()


def launch(seed: int | None = None) -> int:
    """Ouvre l'éditeur graphique. Renvoie un code de sortie."""
    try:
        app = ArtGeneratorApp(seed=seed)
    except tk.TclError as exc:  # pragma: no cover - environnement sans écran
        print(f"Interface graphique indisponible : {exc}")
        return 1
    app.mainloop()
    return 0
