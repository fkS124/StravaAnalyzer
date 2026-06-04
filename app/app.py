"""
app.py - Serveur Flask qui sert la heatmap folium avec une IHM web.

Lance le serveur :
    python app.py
    python app.py --csv activities.csv --gpx GPX

Puis ouvre http://localhost:5000 dans ton navigateur.

Architecture (classes du diagramme) :
    - Analyzer (cette classe) -> orchestre tout
    - Menu, DragAndExploitTool, TemporaryTable -> côté client (HTML/JS)
    - FileManager, FilterManager, SortManager, SearchEngine, Heatmap -> côté Python
"""
import argparse
import os
import webbrowser
from threading import Timer

from flask import Flask, jsonify, render_template, request

from models import User, Point, Zone
from file_manager import FileManager
from filter_manager import FilterManager
from sort_manager import SortManager
from search_engine import SearchEngine
from heatmap import Heatmap


# ----------------------------------------------------------------------
# Analyzer - classe principale (cf. diagramme)
# ----------------------------------------------------------------------
class Analyzer:
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

        print(f"[Analyzer] {len(self.users_by_id)} athlètes")
        total_pts = sum(len(a.track) for a in self.activities)
        print(f"[Analyzer] {total_pts} points GPX au total")

    def _build_users(self):
        """Construit la table des utilisateurs à partir des activités."""
        users = {}
        for a in self.activities:
            if a.athleteId not in users:
                users[a.athleteId] = User(a.athleteId, a.athleteName, "")
            users[a.athleteId].activities.append(a)
        return users


# ---------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------
app = Flask(__name__)
viz = None  # initialisée dans main()


# ----- Page principale : heatmap folium + UI HTML/JS superposée -----
@app.route("/")
def index():
    return render_template("index.html")


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
    parser = argparse.ArgumentParser(description="Strava Analyzer")
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
    viz = Analyzer(csv_path, gpx_dir=gpx_dir,
                     demo=args.demo, dataset_label=args.dataset_label)

    shown_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    url = f"http://{shown_host}:{args.port}"
    print(f"\n{'='*50}")
    print(f"  Strava Analyzer" + ("  [MODE DÉMO]" if args.demo else ""))
    print(f"  -> {url}")
    print(f"{'='*50}\n")

    # En conteneur (host 0.0.0.0) on n'ouvre jamais de navigateur.
    if not args.no_browser and args.host not in ("0.0.0.0",):
        Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
