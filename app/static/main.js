// ============== Carte Leaflet ==============
const map = L.map('map').setView([48.8566, 2.3522], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap', maxZoom: 19,
}).addTo(map);

let heatLayer = null;
let denseLayer = L.layerGroup();
let interLayer = L.layerGroup();
let trackLayer = L.layerGroup();
let drawnZone = null;
let zoneStr = "";
let denseVisible = false;
let tracksVisible = false;

// ============== Outil de dessin (DragAndExploitTool) ==============
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);
const drawControl = new L.Control.Draw({
  position: 'topright',
  draw: {
    rectangle: { shapeOptions: { color: '#fc4c02', weight: 2 } },
    polygon: false, polyline: false, circle: false, marker: false, circlemarker: false,
  },
  edit: { featureGroup: drawnItems, edit: false, remove: true },
});
map.addControl(drawControl);

map.on(L.Draw.Event.CREATED, function (e) {
  drawnItems.clearLayers();
  drawnItems.addLayer(e.layer);
  drawnZone = e.layer;
  const b = e.layer.getBounds();
  const tl = b.getNorthWest(), br = b.getSouthEast();
  zoneStr = `${tl.lat},${tl.lng},${br.lat},${br.lng}`;
  setStatus(`Zone sélectionnée.`);
  applyFilters();
});
map.on(L.Draw.Event.DELETED, function () {
  drawnZone = null; zoneStr = "";
  setStatus("Zone effacée.");
  applyFilters();
});

function clearZone() {
  drawnItems.clearLayers();
  drawnZone = null; zoneStr = "";
  applyFilters();
}

// ============== Récup des paramètres de filtres ==============
function buildQuery(extra) {
  const p = new URLSearchParams();
  const name = document.getElementById('fName').value.trim();
  const type = document.getElementById('fType').value;
  if (name) p.set('name', name);
  if (type) p.set('type', type);
  if (zoneStr) p.set('zone', zoneStr);
  if (extra) for (const k in extra) p.set(k, extra[k]);
  return p.toString();
}

// ============== Heatmap ==============
async function loadHeatmap() {
  setStatus("Chargement de la heatmap...");
  const r = await fetch('/api/heatmap?' + buildQuery());
  const data = await r.json();
  if (heatLayer) map.removeLayer(heatLayer);
  if (data.points.length > 0) {
    heatLayer = L.heatLayer(data.points, { radius: 12, blur: 15, minOpacity: 0.4 });
    heatLayer.addTo(map);
  }
  setStatus(`${data.count} activités, ${data.totalPoints} points GPX.`);
}

// ============== Traces individuelles ==============
const TRACK_COLORS = ['#fc4c02', '#0277fc', '#02c47b', '#9b02fc', '#fc8b02',
                      '#02b8fc', '#fc02a8', '#5a5a5a', '#c4c402', '#02fc8b'];
async function loadTracks() {
  trackLayer.clearLayers();
  const r = await fetch('/api/tracks?' + buildQuery());
  const tracks = await r.json();
  // couleur par athlète
  const userColors = {};
  let ci = 0;
  tracks.forEach(t => {
    if (!(t.athleteId in userColors)) {
      userColors[t.athleteId] = TRACK_COLORS[ci % TRACK_COLORS.length];
      ci++;
    }
    L.polyline(t.points, {
      color: userColors[t.athleteId], weight: 3, opacity: 0.7,
    }).bindPopup(
      `<b>${t.name || t.id}</b><br>${t.athleteName}<br>${t.type} — ${t.date}`
    ).addTo(trackLayer);
  });
  trackLayer.addTo(map);
}
function toggleTracks() {
  tracksVisible = !tracksVisible;
  const btn = document.getElementById('trackBtn');
  if (tracksVisible) {
    loadTracks();
    btn.textContent = "Masquer les traces";
  } else {
    map.removeLayer(trackLayer);
    trackLayer.clearLayers();
    btn.textContent = "Afficher les traces";
  }
}

// ============== Filtres ==============
function applyFilters() {
  loadHeatmap();
  if (denseVisible) loadDenseZones();
  if (tracksVisible) loadTracks();
  if (document.getElementById('tableBox').style.display !== 'none') {
    loadTable();
  }
}
function resetFilters() {
  document.getElementById('fName').value = '';
  document.getElementById('fType').value = '';
  clearZone();
}

// ============== Zones denses ==============
async function loadDenseZones() {
  denseLayer.clearLayers();
  const r = await fetch('/api/dense_zones?' + buildQuery());
  const zones = await r.json();
  if (zones.length === 0) {
    setStatus("Aucune zone dense détectée.");
    return;
  }
  const maxCount = Math.max(...zones.map(z => z.count));
  zones.forEach(z => {
    const ratio = z.count / maxCount;
    const color = ratio < 0.33 ? 'green' : (ratio < 0.66 ? 'orange' : 'red');
    L.circle([z.lat, z.lon], {
      radius: z.radiusKm * 1000, color, fillColor: color,
      fillOpacity: 0.25 + 0.4 * ratio, weight: 2,
    }).bindPopup(
      `<b>Zone dense</b><br>activités : ${z.count}<br>athlètes : ${z.users.length}`
    ).addTo(denseLayer);
  });
  denseLayer.addTo(map);
  setStatus(`${zones.length} zones denses détectées.`);
}
function toggleDenseZones() {
  denseVisible = !denseVisible;
  const btn = document.getElementById('dzBtn');
  if (denseVisible) {
    loadDenseZones();
    btn.textContent = "Masquer les zones denses";
  } else {
    map.removeLayer(denseLayer);
    denseLayer.clearLayers();
    btn.textContent = "Afficher les zones denses";
  }
}

// ============== Intersections ==============
async function showIntersections() {
  interLayer.clearLayers();
  const u1 = document.getElementById('u1').value;
  const u2 = document.getElementById('u2').value;
  if (!u1 || !u2 || u1 === u2) {
    setStatus("Sélectionne deux athlètes différents.");
    return;
  }
  setStatus("Détection en cours...");
  const r = await fetch(`/api/intersections?user1=${encodeURIComponent(u1)}&user2=${encodeURIComponent(u2)}`);
  const inter = await r.json();
  if (inter.length === 0) {
    setStatus(`Aucune intersection entre ${u1} et ${u2}.`);
    return;
  }
  inter.forEach(i => {
    L.marker([i.lat, i.lon], {
      icon: L.divIcon({
        html: '🤝', className: 'inter-icon',
        iconSize: [24, 24], iconAnchor: [12, 12],
      })
    }).bindPopup(
      `<b>Intersection</b><br>Date : ${i.date}<br>Athlètes : ${i.users.join(', ')}`
    ).addTo(interLayer);
  });
  interLayer.addTo(map);
  setStatus(`${inter.length} intersection(s) trouvée(s).`);
}

// ============== Tableau (TemporaryTable) ==============
async function loadTable() {
  const r = await fetch('/api/activities?' + buildQuery());
  const data = await r.json();
  const tbody = document.querySelector('#actTable tbody');
  tbody.innerHTML = '';
  data.forEach(a => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${a.id}</td><td>${a.athleteName}</td>
      <td>${(a.name||'').slice(0,30)}</td><td>${a.type}</td>
      <td>${a.date}</td><td>${(a.location||'').slice(0,20)}</td>
      <td>${a.kudoers}</td><td>${a.trackLength}</td>
    `;
    tbody.appendChild(tr);
  });
}
function toggleTable() {
  const box = document.getElementById('tableBox');
  if (box.style.display === 'none' || box.style.display === '') {
    box.style.display = 'block';
    loadTable();
  } else {
    box.style.display = 'none';
  }
}

// ============== Tri (SortManager) ==============
async function showSort(mode) {
  const r = await fetch(`/api/sort?mode=${mode}&` + buildQuery());
  const data = await r.json();
  document.getElementById('sortTitle').textContent = `Tri par ${data.label}`;
  const tbody = document.querySelector('#sortTable tbody');
  tbody.innerHTML = '';
  data.ranking.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${idx+1}</td><td>${row.name}</td><td>${row.value}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById('sortBox').style.display = 'block';
}

// ============== Status ==============
function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

// ============== Initialisation ==============
async function init() {
  // méta : bandeau "données de démonstration"
  try {
    const rm = await fetch('/api/meta');
    const meta = await rm.json();
    if (meta.demo) {
      document.body.classList.add('demo');
      document.getElementById('demoBanner').style.display = 'block';
      const lbl = meta.datasetLabel ? ` — ${meta.datasetLabel}` : '';
      document.querySelector('#demoBanner span').textContent =
        `⚠️ DONNÉES DE DÉMONSTRATION — FICTIVES (aucune personne réelle)${lbl}`;
    }
  } catch (e) { /* méta indisponible : on continue */ }

  // utilisateurs
  const ru = await fetch('/api/users');
  const users = await ru.json();
  const u1sel = document.getElementById('u1');
  const u2sel = document.getElementById('u2');
  users.forEach(u => {
    const o1 = document.createElement('option');
    o1.value = u.id;
    o1.textContent = `${u.name} (${u.nb_activities})`;
    u1sel.appendChild(o1);
    u2sel.appendChild(o1.cloneNode(true));
  });
  if (users.length >= 2) u2sel.selectedIndex = 1;

  // types
  const rt = await fetch('/api/types');
  const types = await rt.json();
  const tsel = document.getElementById('fType');
  types.forEach(t => {
    const o = document.createElement('option');
    o.value = t; o.textContent = t;
    tsel.appendChild(o);
  });

  await loadHeatmap();
}
init();
