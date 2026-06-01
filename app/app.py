"""
app.py - Serveur Flask qui sert la heatmap folium avec une IHM web.

Lance le serveur :
    python app.py
    python app.py --csv activities.csv --gpx GPX

Puis ouvre http://localhost:5000 dans ton navigateur.

Architecture (classes du diagramme) :
    - Visualizer (cette classe) -> orchestre tout
    - Menu, DragAndExploitTool, TemporaryTable -> côté client (HTML/JS)
    - FileManager, FilterManager, SortManager, SearchEngine, Heatmap -> côté Python
"""
import argparse
import os
import webbrowser
from threading import Timer

from flask import Flask, jsonify, render_template_string, request

from models import User, Point, Zone
from file_manager import FileManager
from filter_manager import FilterManager
from sort_manager import SortManager
from search_engine import SearchEngine
from heatmap import Heatmap


# ----------------------------------------------------------------------
# Visualizer - classe principale (cf. diagramme)
# ----------------------------------------------------------------------
class Visualizer:
    """
    Diagramme :
        - menu, dragTool, tempTable
        + displayHeatmap, displayIntersections, displayDenseZones, showUI
    """

    def __init__(self, csv_path, gpx_dir=None, demo=False, dataset_label=""):
        # Mode démonstration : bandeau d'avertissement dans l'IHM (cf. /api/meta)
        self.demo = demo
        self.dataset_label = dataset_label
        # Services (classes du diagramme)
        self.fileManager = FileManager(gpx_dir=gpx_dir)
        self.heatmap = Heatmap()
        self.searchEngine = SearchEngine()
        self.sortManager = SortManager()

        # Données
        self.activities = self.fileManager.importCSV(csv_path)
        self.users_by_id = self._build_users()
        self.filterManager = FilterManager(users_by_id=self.users_by_id)

        print(f"[Visualizer] {len(self.users_by_id)} athlètes")
        total_pts = sum(len(a.track) for a in self.activities)
        print(f"[Visualizer] {total_pts} points GPX au total")

    def _build_users(self):
        """Construit la table des utilisateurs à partir des activités."""
        users = {}
        for a in self.activities:
            if a.athleteId not in users:
                users[a.athleteId] = User(a.athleteId, a.athleteName, "")
            users[a.athleteId].activities.append(a)
        return users


# ----------------------------------------------------------------------
# Flask app
# ----------------------------------------------------------------------
app = Flask(__name__)
viz = None  # initialisée dans main()


# ----- Page principale : heatmap folium + UI HTML/JS superposée -----
@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


# ----- API : liste des utilisateurs (pour les menus déroulants) -----
@app.route("/api/users")
def api_users():
    return jsonify([
        {"id": u.id, "name": u.name, "gender": u.gender,
         "nb_activities": len(u.activities)}
        for u in sorted(viz.users_by_id.values(), key=lambda x: x.name.lower())
    ])


# ----- API : types d'activités disponibles -----
@app.route("/api/types")
def api_types():
    types = sorted({a.type for a in viz.activities if a.type})
    return jsonify(types)


# ----- API : méta-info (mode démo / libellé du jeu de données) -----
@app.route("/api/meta")
def api_meta():
    return jsonify({
        "demo": viz.demo,
        "datasetLabel": viz.dataset_label,
        "nbActivities": len(viz.activities),
        "nbAthletes": len(viz.users_by_id),
    })


# ----- API : points pour la heatmap (tous les points des traces filtrées) -----
@app.route("/api/heatmap")
def api_heatmap():
    activities = _apply_filters(viz.activities, request.args)
    points = []
    for a in activities:
        for p in a.track:
            points.append([p.latitude, p.longitude])
    return jsonify({
        "points": points,
        "count": len(activities),
        "totalPoints": len(points),
    })


# ----- API : traces individuelles (polylignes) -----
@app.route("/api/tracks")
def api_tracks():
    activities = _apply_filters(viz.activities, request.args)
    # cap à 50 traces pour ne pas saturer le navigateur
    activities = activities[:50]
    return jsonify([
        {
            "id": a.id,
            "athleteName": a.athleteName,
            "athleteId": a.athleteId,
            "type": a.type,
            "name": a.name,
            "date": a.date.isoformat() if a.date else "",
            "points": [[p.latitude, p.longitude] for p in a.track],
        } for a in activities
    ])


# ----- API : table d'activités filtrées (TemporaryTable côté client) -----
@app.route("/api/activities")
def api_activities():
    activities = _apply_filters(viz.activities, request.args)
    activities = activities[:200]
    return jsonify([a.to_dict() for a in activities])


# ----- API : zones denses (DenseZone) -----
@app.route("/api/dense_zones")
def api_dense_zones():
    activities = _apply_filters(viz.activities, request.args)
    zones = viz.searchEngine.findDenseZones(activities)
    return jsonify([
        {
            "lat": z.center.latitude,
            "lon": z.center.longitude,
            "radiusKm": z.radiusKm,
            "count": z.activityCount,
            "users": z.userIds,
        } for z in zones
    ])


# ----- API : intersections entre 2 utilisateurs -----
@app.route("/api/intersections")
def api_intersections():
    u1 = request.args.get("user1", "").strip()
    u2 = request.args.get("user2", "").strip()
    if not u1 or not u2:
        return jsonify([])
    a1 = [a for a in viz.activities if a.athleteId == u1]
    a2 = [a for a in viz.activities if a.athleteId == u2]
    inter = viz.searchEngine.detectIntersections(a1, a2)
    return jsonify([
        {
            "date": (i.getDate().isoformat() if i.getDate() else ""),
            "lat": i.getLocation().latitude,
            "lon": i.getLocation().longitude,
            "users": i.getUserIds(),
        } for i in inter
    ])


# ----- API : tri par utilisateur -----
@app.route("/api/sort")
def api_sort():
    mode = request.args.get("mode", "count")
    activities = _apply_filters(viz.activities, request.args)
    if mode == "duration":
        ranking = viz.sortManager.sortByTotalDuration(activities)
        label = "durée totale (s)"
    else:
        ranking = viz.sortManager.sortByActivityCount(activities)
        label = "nombre d'activités"
    return jsonify({
        "label": label,
        "ranking": [
            {
                "userId": uid,
                "name": viz.users_by_id.get(uid).name if uid in viz.users_by_id else uid,
                "value": val,
            } for uid, val in ranking
        ]
    })


# ----- Helper : applique les filtres reçus en query string -----
def _apply_filters(activities, args):
    """Applique successivement les filtres via FilterManager (cf. diagramme)."""
    name   = args.get("name", "").strip()
    gender = args.get("gender", "").strip()
    atype  = args.get("type", "").strip()
    zone_str = args.get("zone", "").strip()

    result = list(activities)
    if name:
        result = viz.filterManager.filterByName(result, name)
    if gender:
        result = viz.filterManager.filterByGender(result, gender)
    if atype:
        result = viz.filterManager.filterByActivityType(result, atype)
    if zone_str:
        try:
            lat1, lon1, lat2, lon2 = [float(x) for x in zone_str.split(",")]
            zone = Zone(Point(lat1, lon1), Point(lat2, lon2))
            result = viz.filterManager.filterByZone(result, zone)
        except (ValueError, IndexError):
            pass
    return result


# ----------------------------------------------------------------------
# IHM HTML/CSS/JS
# ----------------------------------------------------------------------
INDEX_HTML = r"""
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Strava Heatmap Visualizer</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"/>
<script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>

<style>
  html, body { margin:0; padding:0; height:100%; font-family: system-ui, sans-serif; }
  #map { position:absolute; top:0; bottom:0; left:0; right:0; z-index:0; }

  #panel {
    position:absolute; top:12px; left:12px; z-index:1000;
    width: 320px; max-height: calc(100% - 24px); overflow-y:auto;
    background: rgba(255,255,255,0.97); border-radius: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2); padding: 14px;
  }
  #panel h1 { font-size: 18px; margin: 0 0 10px 0; color:#fc4c02; }
  #panel h2 { font-size: 14px; margin: 14px 0 6px 0; color:#333;
              border-bottom:1px solid #eee; padding-bottom:4px; }
  #panel label { display:block; font-size:12px; color:#555; margin-top:6px; }
  #panel input, #panel select {
    width:100%; box-sizing:border-box; padding:6px 8px;
    border:1px solid #ccc; border-radius:6px; font-size:13px;
  }
  #panel button {
    margin-top:8px; padding:8px 10px; border:none; border-radius:6px;
    background:#fc4c02; color:white; cursor:pointer; font-size:13px;
    font-weight:600; transition: background 0.15s;
  }
  #panel button:hover { background:#d63f02; }
  #panel button.secondary { background:#666; }
  #panel button.secondary:hover { background:#444; }
  #panel .row { display:flex; gap:6px; }
  #panel .row > * { flex:1; }
  #status {
    margin-top:10px; padding:6px 8px; background:#f4f4f4;
    border-radius:6px; font-size:12px; color:#444;
  }

  #tableBox {
    position:absolute; bottom:12px; left:12px; right:360px; z-index:1000;
    max-height: 220px; overflow:auto;
    background: rgba(255,255,255,0.97); border-radius:10px;
    box-shadow:0 4px 16px rgba(0,0,0,0.2); padding:8px; display:none;
  }
  #tableBox table { width:100%; border-collapse: collapse; font-size:11px; }
  #tableBox th, #tableBox td { padding:3px 6px; border-bottom:1px solid #eee; text-align:left; }
  #tableBox th { background:#fc4c02; color:white; position:sticky; top:0; }
  #tableBox .closeBtn {
    position:absolute; top:6px; right:8px; cursor:pointer;
    background:none; border:none; font-size:18px; color:#666;
  }

  #sortBox {
    position:absolute; top:12px; right:12px; z-index:1000;
    width: 280px; max-height: 60%; overflow:auto;
    background: rgba(255,255,255,0.97); border-radius:10px;
    box-shadow:0 4px 16px rgba(0,0,0,0.2); padding:10px; display:none;
  }
  #sortBox table { width:100%; border-collapse:collapse; font-size:12px; }
  #sortBox th, #sortBox td { padding:4px 6px; border-bottom:1px solid #eee; }
  #sortBox th { background:#444; color:white; }
  #sortBox .closeBtn {
    position:absolute; top:6px; right:8px; cursor:pointer;
    background:none; border:none; font-size:18px; color:#666;
  }

  /* Bandeau "données de démonstration" */
  #demoBanner {
    position:absolute; top:0; left:0; right:0; z-index:1500;
    background: repeating-linear-gradient(45deg,#ffc107,#ffc107 18px,#111 18px,#111 36px);
    color:#fff; text-align:center; font-weight:800; font-size:13px;
    letter-spacing:0.5px; padding:6px 12px; display:none;
    text-shadow:0 0 4px #000, 0 0 4px #000; box-shadow:0 2px 8px rgba(0,0,0,0.4);
  }
  #demoBanner span { background:rgba(17,17,17,0.85); padding:3px 10px; border-radius:4px; }
  body.demo #panel { top:42px; max-height: calc(100% - 54px); }
  body.demo #sortBox { top:42px; }
</style>
</head>
<body>

<div id="demoBanner"><span>⚠️ DONNÉES DE DÉMONSTRATION — FICTIVES (aucune personne réelle)</span></div>

<div id="map"></div>

<!-- Menu (cf. classe Menu du diagramme) -->
<div id="panel">
  <h1>🏃 Strava Heatmap</h1>

  <h2>🔍 Filtres</h2>
  <label>Nom d'athlète</label>
  <input type="text" id="fName" placeholder="ex: Alice">

  <label>Type d'activité</label>
  <select id="fType"><option value="">— tous —</option></select>

  <div class="row">
    <button onclick="applyFilters()">Appliquer</button>
    <button class="secondary" onclick="resetFilters()">Réinitialiser</button>
  </div>

  <h2>🛤️ Affichage</h2>
  <div class="row">
    <button onclick="toggleTracks()" id="trackBtn">Afficher les traces</button>
  </div>

  <h2>📊 Tri</h2>
  <div class="row">
    <button onclick="showSort('count')">Par nb d'activités</button>
    <button onclick="showSort('duration')">Par durée totale</button>
  </div>

  <h2>🎯 Zones denses</h2>
  <button onclick="toggleDenseZones()" id="dzBtn">Afficher les zones denses</button>

  <h2>🤝 Intersections</h2>
  <label>Athlète 1</label>
  <select id="u1"></select>
  <label>Athlète 2</label>
  <select id="u2"></select>
  <button onclick="showIntersections()">Détecter les intersections</button>

  <h2>✏️ Sélection de zone</h2>
  <p style="font-size:11px; color:#666; margin:0;">Utilise l'outil rectangle (en haut à droite de la carte) pour dessiner une zone.</p>
  <button class="secondary" onclick="clearZone()">Effacer la zone</button>

  <h2>📋 Tableau</h2>
  <button onclick="toggleTable()">Afficher / cacher le tableau</button>

  <div id="status">Chargement...</div>
</div>

<!-- TemporaryTable -->
<div id="tableBox">
  <button class="closeBtn" onclick="document.getElementById('tableBox').style.display='none'">×</button>
  <h3 style="margin:0 0 6px 0; font-size:13px;">Activités filtrées</h3>
  <table id="actTable">
    <thead><tr>
      <th>id</th><th>athlète</th><th>nom</th><th>type</th>
      <th>date</th><th>lieu</th><th>kudos</th><th>pts GPX</th>
    </tr></thead>
    <tbody></tbody>
  </table>
</div>

<!-- Sort result -->
<div id="sortBox">
  <button class="closeBtn" onclick="document.getElementById('sortBox').style.display='none'">×</button>
  <h3 id="sortTitle" style="margin:0 0 6px 0; font-size:13px;">Tri</h3>
  <table id="sortTable">
    <thead><tr><th>#</th><th>Athlète</th><th>Valeur</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<script>
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
</script>
</body>
</html>
"""


# ----------------------------------------------------------------------
# Lancement
# ----------------------------------------------------------------------
def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "oui")


def main():
    # Les valeurs par défaut peuvent venir de variables d'environnement
    # (pratique pour Docker / docker-compose).
    parser = argparse.ArgumentParser(description="Strava Heatmap Visualizer")
    parser.add_argument("--csv", default=os.environ.get("CSV_PATH", "data.csv"),
                        help="Chemin du CSV d'activités (env : CSV_PATH)")
    parser.add_argument("--gpx", default=os.environ.get("GPX_DIR"),
                        help="Dossier des fichiers GPX (env : GPX_DIR)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                        help="Interface d'écoute (env : HOST ; 0.0.0.0 en conteneur)")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "5000")),
                        help="Port d'écoute (env : PORT)")
    parser.add_argument("--demo", action="store_true", default=_env_bool("DEMO"),
                        help="Affiche le bandeau « données de démonstration » (env : DEMO)")
    parser.add_argument("--dataset-label", default=os.environ.get("DATASET_LABEL", ""),
                        help="Libellé du jeu de données affiché dans l'IHM")
    parser.add_argument("--no-browser", action="store_true",
                        default=_env_bool("NO_BROWSER"),
                        help="Ne pas ouvrir le navigateur automatiquement")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    gpx_dir = os.path.abspath(args.gpx) if args.gpx else None

    global viz
    viz = Visualizer(csv_path, gpx_dir=gpx_dir,
                     demo=args.demo, dataset_label=args.dataset_label)

    shown_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    url = f"http://{shown_host}:{args.port}"
    print(f"\n{'='*50}")
    print(f"  Strava Heatmap Visualizer" + ("  [MODE DÉMO]" if args.demo else ""))
    print(f"  -> {url}")
    print(f"{'='*50}\n")

    # En conteneur (host 0.0.0.0) on n'ouvre jamais de navigateur.
    if not args.no_browser and args.host not in ("0.0.0.0",):
        Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
