const gallery = document.querySelector("#gallery");
const statusEl = document.querySelector("#status");
const selectionCount = document.querySelector("#selectionCount");
const selected = new Map();
let lastQuery = "";

const controls = {
  aspect: document.querySelector("#aspectFilter"),
  motif: document.querySelector("#motifFilter"),
  folder: document.querySelector("#folderFilter"),
  query: document.querySelector("#queryInput"),
  image: document.querySelector("#imageQuery"),
  minScore: document.querySelector("#minScore"),
  minScoreLabel: document.querySelector("#minScoreLabel"),
};

// Populate folder filter from API on load
fetch("/api/folder-tags")
  .then((r) => r.json())
  .then((tags) => {
    for (const tag of tags) {
      const opt = document.createElement("option");
      opt.value = tag;
      opt.textContent = tag;
      controls.folder.appendChild(opt);
    }
  })
  .catch(() => {});  // collection may be empty on first load

controls.minScore.addEventListener("input", () => {
  controls.minScoreLabel.textContent = parseFloat(controls.minScore.value).toFixed(2);
  rerunSearch();
});

document.querySelector("#textSearchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  lastQuery = controls.query.value.trim();
  if (!lastQuery) return;
  await textSearch();
});

document.querySelector("#scanButton").addEventListener("click", async () => {
  showProgress();
  setStatus("Scan läuft. Beim ersten Start kann der Modell-Download dauern.");

  // Fire scan — blocks on server side (runs in thread pool), returns when done
  const scanPromise = fetch("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  // Poll /api/scan/status every 500 ms while scan is running
  const pollInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/scan/status");
      const s = await res.json();
      updateProgress(s);
    } catch (_) {
      // ignore transient errors during scan
    }
  }, 500);

  try {
    const response = await scanPromise;
    const data = await response.json();
    clearInterval(pollInterval);
    setStatus(`${data.indexed} Bilder indexiert, ${data.skipped} übersprungen.`);
    // One final poll to show completed state
    const finalStatus = await fetch("/api/scan/status").then((r) => r.json());
    updateProgress(finalStatus);
    setTimeout(hideProgress, 3000);
  } catch (err) {
    clearInterval(pollInterval);
    setStatus("Scan-Fehler: " + err.message);
    hideProgress();
  }
});

function showProgress() {
  document.querySelector("#progressSection").hidden = false;
  document.querySelector("#progressBarFill").style.width = "0%";
  document.querySelector("#progressText").textContent = "Wird gestartet…";
}

function hideProgress() {
  document.querySelector("#progressSection").hidden = true;
}

function updateProgress(s) {
  const pct = s.pct ?? 0;
  document.querySelector("#progressBarFill").style.width = pct + "%";
  let text;
  if (s.running) {
    const speed = s.imgs_per_sec ? ` · ${s.imgs_per_sec} Bilder/s` : "";
    const eta = s.eta_sec != null ? ` · ETA ${fmtEta(s.eta_sec)}` : "";
    text = `${pct} % — ${s.loaded} / ${s.total} geladen · ${s.indexed} indexiert${speed}${eta}`;
  } else {
    text = `Fertig — ${s.indexed} indexiert, ${s.skipped} übersprungen`;
  }
  document.querySelector("#progressText").textContent = text;
}

function fmtEta(sec) {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60), s = sec % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

controls.aspect.addEventListener("change", rerunSearch);
controls.motif.addEventListener("change", rerunSearch);
controls.folder.addEventListener("change", rerunSearch);

controls.image.addEventListener("change", async () => {
  const file = controls.image.files?.[0];
  if (!file) return;
  setStatus("Suche ähnliche Bilder.");
  const params = searchParams();
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`/api/search/image?${params}`, { method: "POST", body });
  render(await response.json());
});

document.querySelector("#exportCsv").addEventListener("click", () => exportShortlist("csv"));
document.querySelector("#exportJson").addEventListener("click", () => exportShortlist("json"));

async function rerunSearch() {
  if (lastQuery) await textSearch();
}

async function textSearch() {
  setStatus("Suche läuft.");
  const params = searchParams();
  params.set("q", lastQuery);
  const response = await fetch(`/api/search/text?${params}`);
  render(await response.json());
}

function searchParams() {
  const params = new URLSearchParams();
  params.set("limit", "80");
  params.set("aspect", controls.aspect.value);
  params.set("min_score", controls.minScore.value);
  if (controls.motif.value) params.set("motif_class", controls.motif.value);
  if (controls.folder.value) params.set("folder_tag", controls.folder.value);
  return params;
}

function render(items) {
  gallery.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    setStatus("Keine Treffer.");
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const tile = document.createElement("article");
    tile.className = `tile ${selected.has(item.id) ? "selected" : ""}`;
    tile.tabIndex = 0;
    tile.innerHTML = `
      <img class="thumb" src="${item.thumbnail_url}" alt="${escapeHtml(item.filename)}" loading="lazy" />
      <div class="meta">
        <div class="filename" title="${escapeHtml(item.path)}">${escapeHtml(item.filename)}</div>
        <div class="chips">
          <span class="chip">${item.aspect_class}</span>
          <span class="chip">${item.motif_class}</span>
        </div>
        <div class="score">${item.score == null ? "" : `Score ${item.score.toFixed(3)}`}</div>
      </div>
    `;
    tile.addEventListener("click", () => toggle(item, tile));
    tile.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle(item, tile);
      }
    });
    fragment.appendChild(tile);
  }
  gallery.appendChild(fragment);
  setStatus(`${items.length} Treffer.`);
}

function toggle(item, tile) {
  if (selected.has(item.id)) {
    selected.delete(item.id);
    tile.classList.remove("selected");
  } else {
    selected.set(item.id, item);
    tile.classList.add("selected");
  }
  updateSelectionCount();
}

async function exportShortlist(format) {
  if (selected.size === 0) {
    setStatus("Keine Bilder ausgewählt.");
    return;
  }
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...selected.keys()], format }),
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `shortlist.${format}`;
  link.click();
  URL.revokeObjectURL(url);
  setStatus(`Shortlist als ${format.toUpperCase()} exportiert.`);
}

function updateSelectionCount() {
  selectionCount.textContent = `${selected.size} ausgewählt`;
}

function setStatus(message) {
  statusEl.textContent = message;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
