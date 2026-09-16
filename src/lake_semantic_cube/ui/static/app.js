const state = {
  mode: "point",
  dragging: false,
  start: null,
  currentBox: null,
  shape: null,
  raster: null,
  buoys: [],
};

const mapImage = document.getElementById("mapImage");
const overlay = document.getElementById("overlay");
const ctx = overlay.getContext("2d");
const semanticSelect = document.getElementById("semanticSelect");
const statusEl = document.getElementById("status");
const resultTitle = document.getElementById("resultTitle");
const resultImage = document.getElementById("resultImage");
const summaryGrid = document.getElementById("summaryGrid");
const pointMode = document.getElementById("pointMode");
const boxMode = document.getElementById("boxMode");

function setMode(mode) {
  state.mode = mode;
  pointMode.classList.toggle("active", mode === "point");
  boxMode.classList.toggle("active", mode === "box");
  clearOverlay();
}

function resizeCanvas() {
  const rect = overlay.getBoundingClientRect();
  overlay.width = Math.round(rect.width * window.devicePixelRatio);
  overlay.height = Math.round(rect.height * window.devicePixelRatio);
  ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
  redraw();
}

function normalizedPoint(event) {
  const imageRect = displayedImageRect();
  const nx = Math.min(1, Math.max(0, (event.clientX - imageRect.left) / imageRect.width));
  const ny = Math.min(1, Math.max(0, (event.clientY - imageRect.top) / imageRect.height));
  const map = normalizedToMap(nx, ny);
  return {
    x: map.x,
    y: map.y,
    nx,
    ny,
    px: event.clientX - overlay.getBoundingClientRect().left,
    py: event.clientY - overlay.getBoundingClientRect().top,
  };
}

function displayedImageRect() {
  const rect = overlay.getBoundingClientRect();
  const naturalRatio = mapImage.naturalWidth && mapImage.naturalHeight
    ? mapImage.naturalWidth / mapImage.naturalHeight
    : rect.width / rect.height;
  const boxRatio = rect.width / rect.height;
  let width = rect.width;
  let height = rect.height;
  let left = 0;
  let top = 0;
  if (naturalRatio > boxRatio) {
    height = width / naturalRatio;
    top = (rect.height - height) / 2;
  } else {
    width = height * naturalRatio;
    left = (rect.width - width) / 2;
  }
  return { left, top, width, height };
}

function activeBounds() {
  if (state.raster && state.raster.bbox) return state.raster.bbox;
  if (state.shape && state.shape.bbox) return state.shape.bbox;
  return null;
}

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function normalizedToMap(nx, ny) {
  const b = activeBounds();
  if (!b) return { x: nx, y: ny };
  return {
    x: b.min_x + nx * (b.max_x - b.min_x),
    y: b.max_y - ny * (b.max_y - b.min_y),
  };
}

function mapToPixel(x, y) {
  const imageRect = displayedImageRect();
  const b = activeBounds();
  if (!b) return { px: x * imageRect.width + imageRect.left, py: y * imageRect.height + imageRect.top };
  return {
    px: imageRect.left + ((x - b.min_x) / (b.max_x - b.min_x)) * imageRect.width,
    py: imageRect.top + ((b.max_y - y) / (b.max_y - b.min_y)) * imageRect.height,
  };
}

function clearOverlay() {
  state.currentBox = null;
  state.start = null;
  redraw();
}

function redraw() {
  const rect = overlay.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  drawShape();
  drawBuoys();
  if (state.currentBox) {
    const b = state.currentBox;
    ctx.strokeStyle = "#d94b2b";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(b.x, b.y, b.w, b.h);
    ctx.setLineDash([]);
    ctx.fillStyle = "rgba(217, 75, 43, 0.12)";
    ctx.fillRect(b.x, b.y, b.w, b.h);
  }
}

function drawBuoys() {
  if (!state.buoys || !state.buoys.length) return;
  ctx.save();
  ctx.font = "12px Inter, Segoe UI, Arial, sans-serif";
  state.buoys.forEach((buoy) => {
    const p = mapToPixel(buoy.longitude, buoy.latitude);
    ctx.fillStyle = "#ff6b3a";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(p.px, p.py, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    const label = buoy.stcd || buoy.name || "buoy";
    ctx.fillStyle = "rgba(16, 32, 38, 0.86)";
    ctx.fillRect(p.px + 9, p.py - 16, ctx.measureText(label).width + 10, 19);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, p.px + 14, p.py - 3);
  });
  ctx.restore();
}

function drawShape() {
  if (!state.shape || !state.shape.rings) return;
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
  ctx.lineWidth = 2.5;
  ctx.shadowColor = "rgba(0, 0, 0, 0.45)";
  ctx.shadowBlur = 4;
  state.shape.rings.forEach((ring) => {
    if (!ring.length) return;
    ctx.beginPath();
    ring.forEach(([x, y], index) => {
      const p = mapToPixel(x, y);
      if (index === 0) ctx.moveTo(p.px, p.py);
      else ctx.lineTo(p.px, p.py);
    });
    ctx.closePath();
    ctx.stroke();
  });
  ctx.restore();
}

function renderSummary(summary) {
  summaryGrid.innerHTML = "";
  Object.entries(summary).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = "metric";
    item.innerHTML = `<span>${key.replaceAll("_", " ")}</span><strong>${value}</strong>`;
    summaryGrid.appendChild(item);
  });
}

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function runPoint(point) {
  statusEl.textContent = "Running point semantic query...";
  const payload = {
    semantic: semanticSelect.value,
    x: point.x,
    y: point.y,
  };
  const data = await postJSON("/api/query-point", payload);
  resultTitle.textContent = data.title;
  resultImage.src = data.image;
  resultImage.style.display = "block";
  renderSummary(data.summary);
  statusEl.textContent = `Point query at x=${point.x.toFixed(6)}, y=${point.y.toFixed(6)}`;
}

async function runRegion(box) {
  statusEl.textContent = "Running region semantic query...";
  const imageRect = displayedImageRect();
  const minNx = clamp01((Math.min(box.x, box.x + box.w) - imageRect.left) / imageRect.width);
  const maxNx = clamp01((Math.max(box.x, box.x + box.w) - imageRect.left) / imageRect.width);
  const minNy = clamp01((Math.min(box.y, box.y + box.h) - imageRect.top) / imageRect.height);
  const maxNy = clamp01((Math.max(box.y, box.y + box.h) - imageRect.top) / imageRect.height);
  const topLeft = normalizedToMap(minNx, minNy);
  const bottomRight = normalizedToMap(maxNx, maxNy);
  const payload = {
    semantic: semanticSelect.value,
    box: {
      min_x: Math.min(topLeft.x, bottomRight.x),
      max_x: Math.max(topLeft.x, bottomRight.x),
      min_y: Math.min(topLeft.y, bottomRight.y),
      max_y: Math.max(topLeft.y, bottomRight.y),
    },
  };
  const data = await postJSON("/api/query-region", payload);
  resultTitle.textContent = data.title;
  resultImage.src = data.image;
  resultImage.style.display = "block";
  renderSummary(data.summary);
  statusEl.textContent = "Region query completed";
}

overlay.addEventListener("mousedown", (event) => {
  const p = normalizedPoint(event);
  if (state.mode === "point") {
    clearOverlay();
    ctx.fillStyle = "#d94b2b";
    ctx.beginPath();
    ctx.arc(p.px, p.py, 5, 0, Math.PI * 2);
    ctx.fill();
    runPoint(p).catch((error) => (statusEl.textContent = error.message));
  } else {
    state.dragging = true;
    state.start = p;
    state.currentBox = { x: p.px, y: p.py, w: 0, h: 0 };
    redraw();
  }
});

overlay.addEventListener("mousemove", (event) => {
  if (!state.dragging || state.mode !== "box") return;
  const p = normalizedPoint(event);
  state.currentBox = {
    x: state.start.px,
    y: state.start.py,
    w: p.px - state.start.px,
    h: p.py - state.start.py,
  };
  redraw();
});

window.addEventListener("mouseup", () => {
  if (!state.dragging || state.mode !== "box") return;
  state.dragging = false;
  const box = state.currentBox;
  if (Math.abs(box.w) > 8 && Math.abs(box.h) > 8) {
    runRegion(box).catch((error) => (statusEl.textContent = error.message));
  }
});

pointMode.addEventListener("click", () => setMode("point"));
boxMode.addEventListener("click", () => setMode("box"));
document.getElementById("closeResult").addEventListener("click", () => {
  resultImage.style.display = "none";
  summaryGrid.innerHTML = "";
  resultTitle.textContent = "Semantic Layer Explorer";
  clearOverlay();
});

window.addEventListener("resize", resizeCanvas);

fetch("/api/state")
  .then((response) => response.json())
  .then((data) => {
    state.shape = data.shape;
    state.raster = data.raster;
    state.buoys = data.buoys || [];
    semanticSelect.innerHTML = data.semantics
      .map((item) => `<option value="${item.id}">${item.label} · ${item.variable}</option>`)
      .join("");
    mapImage.src = data.preview;
    const shapeText = data.shape ? ` | reservoir polygon: loaded (${data.shape.crs})` : "";
    const buoyText = state.buoys.length ? ` | buoys: ${state.buoys.map((b) => b.stcd || b.name).join(", ")}` : "";
    statusEl.textContent = data.tif ? `Remote sensing preview loaded${shapeText}${buoyText}` : `Synthetic map preview${shapeText}${buoyText}`;
    redraw();
  });

mapImage.addEventListener("load", resizeCanvas);
setMode("point");
