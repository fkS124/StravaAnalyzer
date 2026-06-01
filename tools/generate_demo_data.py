"""
generate_demo_data.py - Générateur de DONNÉES DE DÉMONSTRATION FICTIVES.

Produit un CSV + des traces GPX synthétiques mais RÉALISTES : les itinéraires
suivent le vrai réseau routier (routage OSRM) autour de Lyon. Les données
restent volontairement identifiables :
  - les athlètes sont préfixés "[DÉMO]" (visibles dans l'IHM) ;
  - le lieu est "Lyon (démo fictive)" et la description le rappelle ;
  - le bandeau d'avertissement de l'IHM reste actif (DEMO=true).

Le scénario intègre exprès :
  - un HUB central (Place Bellecour) traversé par presque toutes les
    activités  -> zones denses ;
  - une INTERSECTION calée dans le temps entre deux athlètes différents qui
    passent Bellecour à la même minute.

Aucune donnée ne correspond à une personne réelle.

Usage :
    python generate_demo_data.py [dossier_sortie]
        dossier_sortie par défaut : ../data/demo

Nécessite un accès Internet (API publique OSRM). En cas d'échec d'une requête,
l'itinéraire bascule sur une interpolation en ligne droite entre les étapes.
"""
import csv
import json
import math
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

random.seed(42)  # reproductibilité

OSRM_BASE = "https://router.project-osrm.org/route/v1"
LOCATION = "Lyon (démo fictive)"

# --- Points d'ancrage réels (lat, lon) dans Lyon ---
BELLECOUR   = (45.7578, 4.8320)   # hub central -> zones denses
TETEDOR     = (45.7740, 4.8520)   # Parc de la Tête d'Or
CONFLUENCE  = (45.7430, 4.8160)
CROIXROUSSE = (45.7740, 4.8290)
PARTDIEU    = (45.7610, 4.8590)
GERLAND     = (45.7270, 4.8290)
VAISE       = (45.7800, 4.8050)
GUILLOTIERE = (45.7560, 4.8430)

# Vitesses réalistes (m/s) selon le type d'activité
SPEED = {"Run": 3.0, "Ride": 6.5, "Walk": 1.4}

# Athlètes fictifs (noms volontairement marqués)
A1 = ("U_DEMO_1", "[DÉMO] Camille Laurent")
A2 = ("U_DEMO_2", "[DÉMO] Karim Benali")
A3 = ("U_DEMO_3", "[DÉMO] Léa Moreau")
A4 = ("U_DEMO_4", "[DÉMO] Hugo Petit")
A5 = ("U_DEMO_5", "[DÉMO] Sofia Garcia")


def haversine_m(p1, p2):
    R = 6371000.0
    la1, lo1 = math.radians(p1[0]), math.radians(p1[1])
    la2, lo2 = math.radians(p2[0]), math.radians(p2[1])
    dla, dlo = la2 - la1, lo2 - lo1
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ----------------------------------------------------------------------
# Routage
# ----------------------------------------------------------------------
def _straight(waypoints, step_m=20):
    """Repli : ligne droite densifiée entre les étapes."""
    out = []
    for a, b in zip(waypoints[:-1], waypoints[1:]):
        d = haversine_m(a, b)
        n = max(2, int(d / step_m))
        for i in range(n):
            out.append((a[0] + (b[0] - a[0]) * i / n,
                        a[1] + (b[1] - a[1]) * i / n))
    out.append(waypoints[-1])
    return out


def osrm_route(waypoints, profile):
    """Itinéraire suivant les routes réelles (liste de (lat, lon))."""
    coords = ";".join(f"{lon},{lat}" for (lat, lon) in waypoints)
    url = (f"{OSRM_BASE}/{profile}/{coords}"
           f"?overview=full&geometries=geojson")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.load(r)
        if data.get("code") != "Ok":
            raise ValueError(data.get("code"))
        geom = data["routes"][0]["geometry"]["coordinates"]
        pts = [(lat, lon) for (lon, lat) in geom]   # OSRM = [lon, lat]
        if len(pts) < 2:
            raise ValueError("trop court")
        return pts
    except Exception as e:                          # repli hors-ligne
        print(f"  [!] OSRM indisponible ({e}) -> ligne droite")
        return _straight(waypoints)


def add_gps_jitter(pts, sigma_deg=0.000025):
    """Léger bruit GPS (~2-3 m) pour un rendu réaliste."""
    return [(la + random.gauss(0, sigma_deg),
             lo + random.gauss(0, sigma_deg)) for (la, lo) in pts]


def timed_track(pts, speed_mps):
    """Associe à chaque point un décalage temporel (s) à vitesse ~ variable."""
    offsets = [0.0]
    t = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        d = haversine_m(a, b)
        v = speed_mps * random.uniform(0.8, 1.2)    # allure organique
        t += d / max(v, 0.5)
        offsets.append(t)
    return offsets


def nearest_offset(pts, offsets, anchor):
    """Décalage temporel du point le plus proche d'un point d'ancrage."""
    best_i, best_d = 0, float("inf")
    for i, p in enumerate(pts):
        d = haversine_m(p, anchor)
        if d < best_d:
            best_d, best_i = d, i
    return offsets[best_i]


def write_gpx(path, pts, offsets, start_dt):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gpx version="1.1" creator="generate_demo_data (FICTIF)" '
                'xmlns="http://www.topografix.com/GPX/1/1">\n  <trk>'
                '<name>DEMO</name><trkseg>\n')
        for (la, lo), off in zip(pts, offsets):
            t = start_dt + timedelta(seconds=off)
            f.write(f'    <trkpt lat="{la:.6f}" lon="{lo:.6f}">'
                    f'<time>{t.strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>\n')
        f.write('  </trkseg></trk>\n</gpx>\n')


# ----------------------------------------------------------------------
# Scénario
# ----------------------------------------------------------------------
def build_individual_specs():
    """Activités solo, étalées sur janvier. (id, athlète, type, date, nom, [étapes], with)."""
    d = lambda day, h=8, m=0: datetime(2025, 1, day, h, m, 0)
    return [
        # Camille (course)
        ("D001", A1, "Run",  d(6),  "Boucle Tête d'Or",     [TETEDOR, CROIXROUSSE, BELLECOUR], []),
        ("D002", A1, "Run",  d(8),  "Sortie quais",         [BELLECOUR, GUILLOTIERE, GERLAND], []),
        # Karim (vélo)
        ("D003", A2, "Ride", d(9),  "Tour de Gerland",      [GERLAND, CONFLUENCE, BELLECOUR], []),
        ("D004", A2, "Ride", d(15), "Part-Dieu express",    [PARTDIEU, GUILLOTIERE, BELLECOUR], []),
        # Léa (course)
        ("D005", A3, "Run",  d(10), "Traversée Vaise",      [GUILLOTIERE, BELLECOUR, VAISE], []),
        ("D006", A3, "Run",  d(14), "Retour Confluence",    [CONFLUENCE, BELLECOUR], []),
        # Hugo (course / vélo)
        ("D007", A4, "Run",  d(12), "Retour Part-Dieu",     [PARTDIEU, BELLECOUR], []),
        ("D008", A4, "Ride", d(16), "Croix-Rousse à vélo",  [GERLAND, BELLECOUR, CROIXROUSSE], []),
        # Sofia (mixte)
        ("D009", A5, "Ride", d(7, 18), "Vélo du soir",      [VAISE, BELLECOUR, PARTDIEU], []),
        ("D010", A5, "Run",  d(9, 19), "Footing parc",      [BELLECOUR, CONFLUENCE, GERLAND], []),
    ]


# Sortie de groupe : tous les athlètes courent LA MÊME boucle, départs
# échelonnés (< 2 min) -> de nombreuses paires se croisent (intersections).
GROUP_DATE = datetime(2025, 1, 20, 8, 0, 0)
GROUP_LOOP = [BELLECOUR, TETEDOR, CROIXROUSSE, BELLECOUR]
GROUP_MEMBERS = [
    # (id, athlète, décalage de départ en secondes, nom)
    ("D101", A1,   0, "Sortie club du dimanche"),
    ("D102", A2,  45, "Sortie club du dimanche"),
    ("D103", A3,  30, "Sortie club du dimanche"),
    ("D104", A4,  90, "Sortie club du dimanche"),
    ("D105", A5,  60, "Sortie club du dimanche"),
]


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "demo")
    out_dir = os.path.abspath(out_dir)
    gpx_dir = os.path.join(out_dir, "GPX")
    os.makedirs(gpx_dir, exist_ok=True)

    # Nettoie les anciennes traces (formes géométriques de la version précédente)
    for f in os.listdir(gpx_dir):
        if f.endswith(".gpx"):
            os.remove(os.path.join(gpx_dir, f))

    indiv = build_individual_specs()
    print(f"[demo] routage de {len(indiv)} activités solo + 1 boucle de groupe...")

    rows = []

    def emit(aid, ath, atype, name, pts, offs, start_dt, wa):
        write_gpx(os.path.join(gpx_dir, f"{aid}.gpx"), pts, offs, start_dt)
        rows.append([
            aid, ath[1], atype, start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            ath[0], name, LOCATION, random.randint(0, 30),
            "DONNÉE DE DÉMONSTRATION — FICTIVE", ";".join(wa),
        ])

    # 1) activités solo (un itinéraire OSRM chacune)
    for (aid, ath, atype, date, name, wps, wa) in indiv:
        profile = "bike" if atype == "Ride" else "foot"
        pts = add_gps_jitter(osrm_route(wps, profile))
        offs = timed_track(pts, SPEED.get(atype, 3.0))
        emit(aid, ath, atype, name, pts, offs, date, wa)
        time.sleep(0.3)  # politesse envers l'API publique

    # 2) sortie de groupe : UNE seule géométrie OSRM, partagée par tous,
    #    avec un bruit GPS / une allure propres à chacun et des départs
    #    échelonnés -> garantit des intersections entre presque toutes les paires.
    loop = osrm_route(GROUP_LOOP, "foot")
    others = [m[1][0] for m in GROUP_MEMBERS]
    for (aid, ath, off_s, name) in GROUP_MEMBERS:
        pts = add_gps_jitter(loop)
        offs = timed_track(pts, SPEED["Run"])
        start_dt = GROUP_DATE + timedelta(seconds=off_s)
        wa = [u for u in others if u != ath[0]]
        emit(aid, ath, "Run", name, pts, offs, start_dt, wa)

    csv_path = os.path.join(out_dir, "data.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["activity_id", "athlete_name", "activity_type",
                    "activity_date", "athlete_id", "activity_name",
                    "activity_location", "activity_kudoers",
                    "activity_description", "with_athletes"])
        w.writerows(rows)

    print(f"[demo] {len(rows)} activités écrites dans {out_dir}")
    print(f"[demo] sortie de groupe {GROUP_DATE:%Y-%m-%d} (5 athlètes) "
          f"-> intersections multiples")


if __name__ == "__main__":
    main()
