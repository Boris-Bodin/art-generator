"""Interface graphique Tkinter (Phase 6) — la *vue*.

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
import queue
import random
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk

from ..core.genome import ArtworkGenome
from ..equations import registry
from ..exporters import genome_io, image as image_export
from ..generators import navigation
from ..generators.genome_generator import generate
from ..palettes import procedural
from ..presets import library
from . import preview

_BACKGROUNDS = ["black", "white", "gradient", "radial"]
_BLEND_MODES = ["normal", "add", "screen", "multiply", "difference"]
_RENDER_MODELS = ["light", "ink"]
_COLOR_BY = ["velocity", "t", "radius"]
_FRAMINGS = ["box", "density"]
_SYMMETRIES = ["none", "mirror", "radial", "kaleidoscope"]
_NOISE_TYPES = ["none", "perlin", "simplex", "fbm", "worley"]

_DEBOUNCE_MS = 120


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

        self._loading = False          # supprime les callbacks pendant un remplissage programmatique
        self._render_job: str | None = None
        self._request_id = 0
        self._result_q: queue.Queue = queue.Queue()
        self._photo: ImageTk.PhotoImage | None = None

        self._build_ui()
        self._refresh_all()
        self.after(50, self._poll_results)
        self._schedule_render()

    # -- construction de l'interface -----------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

    def _labelled_scale(self, parent, label, lo, hi, command):
        """Ligne étiquette + curseur ; renvoie la ``DoubleVar`` liée."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.DoubleVar()
        scale = ttk.Scale(row, from_=lo, to=hi, variable=var,
                          command=lambda _v: command(var.get()))
        scale.pack(side="left", fill="x", expand=True)
        return var

    def _labelled_combo(self, parent, label, values, command):
        """Ligne étiquette + combobox ; renvoie la ``StringVar`` liée."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)
        combo.bind("<<ComboboxSelected>>", lambda _e: command(var.get()))
        return var

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
        ttk.Button(seed_row, text="◀", width=3, command=lambda: self._step_seed(-1)).pack(side="left")
        ttk.Button(seed_row, text="▶", width=3, command=lambda: self._step_seed(1)).pack(side="left")

        ttk.Button(panel, text="Seed aléatoire", command=self._random_seed).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Naviguer", font=("", 10, "bold")).pack(anchor="w")
        ttk.Button(panel, text="Muter (voisin)", command=self._mutate).pack(fill="x", pady=2)
        ttk.Button(panel, text="Re-tirer les formes", command=self._reroll).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Presets", font=("", 10, "bold")).pack(anchor="w")
        self._preset_var = tk.StringVar(value=library.names()[0])
        ttk.Combobox(panel, textvariable=self._preset_var, values=library.names(),
                     state="readonly").pack(fill="x", pady=2)
        ttk.Button(panel, text="Charger le preset", command=self._load_preset).pack(fill="x", pady=2)
        ttk.Button(panel, text="Enregistrer comme preset…", command=self._save_user_preset).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Fichier", font=("", 10, "bold")).pack(anchor="w")
        ttk.Button(panel, text="Ouvrir JSON…", command=self._open_json).pack(fill="x", pady=2)
        ttk.Button(panel, text="Enregistrer JSON…", command=self._save_json).pack(fill="x", pady=2)
        ttk.Button(panel, text="Exporter l'image…", command=self._export_image).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Fond", font=("", 10, "bold")).pack(anchor="w")
        self._bg_var = self._labelled_combo(panel, "Type", _BACKGROUNDS, self._on_background)
        self._vignette_var = self._labelled_scale(panel, "Vignette", 0.0, 0.6, self._on_vignette)

    def _build_center_panel(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        self._canvas = tk.Label(panel, background="#111111")
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._status = ttk.Label(panel, text="")
        self._status.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _build_right_panel(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=2, sticky="ns")

        ttk.Label(panel, text="Couche", font=("", 11, "bold")).pack(anchor="w")
        self._layer_var = tk.StringVar()
        self._layer_combo = ttk.Combobox(panel, textvariable=self._layer_var, state="readonly")
        self._layer_combo.pack(fill="x", pady=2)
        self._layer_combo.bind("<<ComboboxSelected>>", lambda _e: self._select_layer())

        self._family_var = self._labelled_combo(panel, "Famille", registry.families(), self._on_family)
        ttk.Button(panel, text="Palette aléatoire", command=self._random_palette).pack(fill="x", pady=2)

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._blend_var = self._labelled_combo(panel, "Fusion", _BLEND_MODES, lambda v: self._set_layer("blend_mode", v))
        self._model_var = self._labelled_combo(panel, "Médium", _RENDER_MODELS, lambda v: self._set_layer("render_model", v))
        self._colorby_var = self._labelled_combo(panel, "Couleur par", _COLOR_BY, lambda v: self._set_layer("color_by", v))
        self._framing_var = self._labelled_combo(panel, "Cadrage", _FRAMINGS, lambda v: self._set_layer("framing", v))

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._opacity_var = self._labelled_scale(panel, "Opacité", 0.0, 1.0, lambda v: self._set_layer("opacity", v))
        self._glow_var = self._labelled_scale(panel, "Glow", 0.0, 1.0, lambda v: self._set_layer("glow", v))
        self._exposure_var = self._labelled_scale(panel, "Exposition", 0.4, 2.5, lambda v: self._set_layer("exposure", v))
        self._thickness_var = self._labelled_scale(panel, "Épaisseur", 1.0, 4.0, lambda v: self._set_layer("thickness", v))

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._symmetry_var = self._labelled_combo(panel, "Symétrie", _SYMMETRIES, lambda v: self._set_layer("symmetry", v))
        self._order_var = self._labelled_scale(panel, "Ordre", 2, 12, lambda v: self._set_layer("symmetry_order", int(round(v))))

        ttk.Separator(panel).pack(fill="x", pady=6)
        self._noise_var = self._labelled_combo(panel, "Bruit", _NOISE_TYPES, lambda v: self._set_layer("noise_type", v))
        self._warp_var = self._labelled_scale(panel, "Warp", 0.0, 0.6, lambda v: self._set_layer("warp", v))
        self._cnoise_var = self._labelled_scale(panel, "Bruit coul.", 0.0, 0.6, lambda v: self._set_layer("color_noise", v))
        self._lnoise_var = self._labelled_scale(panel, "Bruit lum.", 0.0, 1.0, lambda v: self._set_layer("light_noise", v))

    # -- synchronisation widgets <-> génome ----------------------------------

    @property
    def _layer(self):
        return self.genome.layers[self._current_layer]

    def _refresh_all(self) -> None:
        """Recharge tous les widgets depuis le génome (sans déclencher de callback)."""
        self._loading = True
        try:
            self._seed_var.set(str(self.genome.seed))
            self._bg_var.set(self.genome.background)
            self._vignette_var.set(float(self.genome.background_params.get("vignette", 0.0)))
            n = len(self.genome.layers)
            self._layer_combo["values"] = [f"Couche {i + 1}/{n}" for i in range(n)]
            self._current_layer = min(self._current_layer, n - 1)
            self._layer_var.set(f"Couche {self._current_layer + 1}/{n}")
            self._refresh_layer()
        finally:
            self._loading = False

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
        if self._loading:
            return
        setattr(self._layer, field, value)
        self._schedule_render()

    def _select_layer(self) -> None:
        label = self._layer_var.get()
        try:
            self._current_layer = int(label.split()[1].split("/")[0]) - 1
        except (IndexError, ValueError):
            self._current_layer = 0
        self._loading = True
        try:
            self._refresh_layer()
        finally:
            self._loading = False

    # -- actions gauche -------------------------------------------------------

    def _set_genome(self, genome: ArtworkGenome) -> None:
        self.genome = genome
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

    def _mutate(self) -> None:
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._set_genome(navigation.mutate(self.genome, self._nav_seed))

    def _reroll(self) -> None:
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._set_genome(navigation.reroll_equations(self.genome, self._nav_seed))

    def _load_preset(self) -> None:
        self._set_genome(library.load(self._preset_var.get()))

    def _save_user_preset(self) -> None:
        name = simpledialog.askstring("Preset", "Nom du preset :", parent=self)
        if not name:
            return
        path = library.save_user_preset(self.genome, name)
        messagebox.showinfo("Preset", f"Enregistré :\n{path}")

    def _open_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Génome JSON", "*.json")])
        if not path:
            return
        try:
            self._set_genome(genome_io.load(path))
        except Exception as exc:  # pragma: no cover - dépend du fichier choisi
            messagebox.showerror("Ouverture", str(exc))

    def _save_json(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Génome JSON", "*.json")])
        if path:
            genome_io.save(self.genome, path)

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
        tint = (0.04, 0.05, 0.12)
        if kind == "gradient":
            return {"top": tint, "bottom": (0.0, 0.0, 0.0), "vignette": vignette}
        return {"inner": tint, "outer": (0.0, 0.0, 0.0), "radius": 0.85, "vignette": vignette}

    def _on_vignette(self, value: float) -> None:
        if self._loading:
            return
        params = dict(self.genome.background_params)
        params["vignette"] = float(value)
        self.genome.background_params = params
        self._schedule_render()

    # -- actions droite -------------------------------------------------------

    def _on_family(self, family: str) -> None:
        if self._loading:
            return
        from ..generators import quality
        from ..core.rng import RNG

        layer = self._layer
        layer.equation_family = family
        self._nav_seed = (self._nav_seed + 1) % (2**31)
        layer.equation_params = quality.viable_params(family, RNG(self._nav_seed))
        self._schedule_render()

    def _random_palette(self) -> None:
        from ..core.rng import RNG

        self._nav_seed = (self._nav_seed + 1) % (2**31)
        self._layer.palette = procedural.random_palette(RNG(self._nav_seed))
        self._schedule_render()

    # -- rendu d'aperçu (débouncé, hors thread principal) --------------------

    def _schedule_render(self) -> None:
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self._render_job = self.after(_DEBOUNCE_MS, self._start_render)

    def _start_render(self) -> None:
        self._render_job = None
        self._request_id += 1
        request_id = self._request_id
        snapshot = copy.deepcopy(self.genome)  # fige l'état pour le thread de travail
        self._status.configure(text="Rendu…")

        def work() -> None:
            start = time.perf_counter()
            try:
                img = preview.render_preview(snapshot, point_cap=preview.DRAFT_POINT_CAP)
                elapsed = time.perf_counter() - start
                self._result_q.put((request_id, img, elapsed, None))
            except Exception as exc:  # pragma: no cover - robustesse UI
                self._result_q.put((request_id, None, 0.0, exc))

        threading.Thread(target=work, daemon=True).start()

    def _poll_results(self) -> None:
        try:
            while True:
                request_id, img, elapsed, exc = self._result_q.get_nowait()
                if request_id != self._request_id:
                    continue  # rendu périmé (le dernier gagne)
                if exc is not None:
                    self._status.configure(text=f"Erreur : {exc}")
                    continue
                self._photo = ImageTk.PhotoImage(img)
                self._canvas.configure(image=self._photo)
                self._status.configure(
                    text=f"{self.genome.width}×{self.genome.height} · aperçu "
                    f"{img.width}×{img.height} · {elapsed:.2f}s"
                )
        except queue.Empty:
            pass
        self.after(50, self._poll_results)


def launch(seed: int | None = None) -> int:
    """Ouvre l'éditeur graphique. Renvoie un code de sortie."""
    try:
        app = ArtGeneratorApp(seed=seed)
    except tk.TclError as exc:  # pragma: no cover - environnement sans écran
        print(f"Interface graphique indisponible : {exc}")
        return 1
    app.mainloop()
    return 0
