"use strict";

/*
 * UI web statique d'Art Generator.
 *
 * Le moteur Python (numpy + Pillow) est exécuté DANS le navigateur via Pyodide
 * (WebAssembly) : aucune image n'est pré-rendue, chaque œuvre est calculée à la
 * volée côté client. Ce script se contente de :
 *   1. charger Pyodide, numpy, Pillow, puis installer le wheel du package ;
 *   2. exécuter public/engine.py (qui expose render_preset / render_seed) ;
 *   3. câbler la liste des presets et le bouton « seed aléatoire ».
 *
 * Pas de saisie de seed, pas d'édition : cette UI est en lecture seule.
 * Le rendu bloque le thread principal (Pyodide y tourne) ; on affiche donc un
 * état « Rendu… » et on laisse le DOM se rafraîchir avant de lancer le calcul.
 */

const els = {
  status: document.getElementById("status"),
  placeholder: document.getElementById("placeholder"),
  artwork: document.getElementById("artwork"),
  presetList: document.getElementById("preset-list"),
  btnRandom: document.getElementById("btn-random"),
  caption: document.getElementById("caption"),
  captionTitle: document.getElementById("caption-title"),
  captionDesc: document.getElementById("caption-desc"),
  captionMeta: document.getElementById("caption-meta"),
};

let pyodide = null;
let py = {}; // fonctions Python exposées
let busy = false;

function setStatus(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("error", isError);
}

/** Active/désactive tous les contrôles pendant un chargement ou un rendu. */
function setControlsDisabled(disabled) {
  els.btnRandom.disabled = disabled;
  els.presetList.querySelectorAll("button").forEach((b) => (b.disabled = disabled));
}

/** Laisse le navigateur peindre l'état « Rendu… » avant l'appel bloquant. */
function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
}

/** Affiche le PNG (base64) et la légende. */
function showArtwork(b64, title, desc, meta, activeName) {
  els.artwork.src = "data:image/png;base64," + b64;
  els.artwork.hidden = false;
  els.placeholder.hidden = true;
  els.captionTitle.textContent = title;
  els.captionDesc.textContent = desc || "";
  els.captionMeta.textContent = meta || "";
  els.caption.hidden = false;
  els.presetList.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.name === activeName)
  );
}

/** Exécute un rendu (fonction Python renvoyant du base64) de façon sérialisée. */
async function runRender(label, fn) {
  if (busy || !pyodide) return;
  busy = true;
  setControlsDisabled(true);
  els.artwork.hidden = true;
  els.placeholder.hidden = false;
  setStatus(label);
  await nextFrame();
  const t0 = performance.now();
  try {
    const result = fn();
    const dt = ((performance.now() - t0) / 1000).toFixed(1);
    result.dt = dt;
    return result;
  } catch (err) {
    console.error(err);
    setStatus("Erreur de rendu : " + err.message, true);
    els.placeholder.hidden = false;
    return null;
  } finally {
    busy = false;
    setControlsDisabled(false);
  }
}

async function renderPreset(name, desc) {
  const out = await runRender(`Rendu du preset « ${name} »…`, () => {
    const b64 = py.render_preset(name);
    return { b64 };
  });
  if (out) showArtwork(out.b64, name, desc, `preset · rendu en ${out.dt} s`, name);
}

async function renderRandom() {
  const seed = Math.floor(Math.random() * 2 ** 31);
  const out = await runRender("Rendu d'une seed aléatoire…", () => {
    const b64 = py.render_seed(seed);
    return { b64 };
  });
  if (out) showArtwork(out.b64, `Seed #${seed}`, "Œuvre tirée au hasard.", `seed ${seed} · rendu en ${out.dt} s`, null);
}

/** Construit la liste des presets (boutons désactivés tant que le moteur charge). */
function buildPresetList(presets) {
  els.presetList.setAttribute("aria-busy", "false");
  els.presetList.innerHTML = "";
  for (const p of presets) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.dataset.name = p.name;
    btn.disabled = true;
    btn.innerHTML = `<span class="pname"></span><span class="pdesc"></span>`;
    btn.querySelector(".pname").textContent = p.name;
    btn.querySelector(".pdesc").textContent = p.description;
    btn.addEventListener("click", () => renderPreset(p.name, p.description));
    li.appendChild(btn);
    els.presetList.appendChild(li);
  }
}

async function boot() {
  // 1) Liste des presets tout de suite (sans attendre Pyodide), pour un affichage rapide.
  let presets = [];
  try {
    presets = await (await fetch("presets.json")).json();
    buildPresetList(presets);
  } catch (e) {
    console.warn("presets.json indisponible, liste reconstruite après chargement.", e);
  }

  // 2) Chargement du moteur Python en WebAssembly.
  const build = await (await fetch("build.json")).json();
  try {
    setStatus("Chargement du moteur Python… (~20 Mo au premier lancement)");
    pyodide = await loadPyodide({
      indexURL: `https://cdn.jsdelivr.net/pyodide/${build.pyodide}/full/`,
    });

    setStatus("Chargement de numpy et Pillow…");
    await pyodide.loadPackage(["numpy", "Pillow", "micropip"]);

    setStatus("Installation du moteur d'art…");
    const wheelUrl = new URL(build.wheel, window.location.href).href;
    console.log("Wheel URL:", wheelUrl);

    const response = await fetch(wheelUrl);
    console.log("Wheel status:", response.status, response.headers.get("content-type"));

    await pyodide.runPythonAsync(`
      import micropip
      await micropip.install(["${wheelUrl}"], keep_going=True)
    `);

    setStatus("Initialisation…");
    const engineCode = await (await fetch("engine.py")).text();
    pyodide.runPython(engineCode);
    py.render_preset = pyodide.globals.get("render_preset");
    py.render_seed = pyodide.globals.get("render_seed");

    // Si presets.json avait échoué, on reconstruit la liste depuis Python.
    if (presets.length === 0) {
      presets = JSON.parse(pyodide.globals.get("presets_json")());
      buildPresetList(presets);
    }
  } catch (err) {
    console.error(err);
    setStatus("Impossible de charger le moteur : " + err.message, true);
    return;
  }

  // 3) Prêt : on active les contrôles et on rend une première œuvre aléatoire.
  setControlsDisabled(false);
  setStatus("Prêt.");
  await renderRandom();
}

boot();
