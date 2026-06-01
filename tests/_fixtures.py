"""
Helpers de tests : construction d'activités synthétiques et géométrie.
"""
import math
import os
import tempfile
from datetime import datetime

from models import Activity, Point


def mk_point(lat, lon, t=None):
    return Point(lat, lon, t)


def mk_activity(aid, athlete_id, points, athlete_name=None, atype="Run",
                date=None, with_athletes=None):
    """Crée une Activity avec une trace donnée (liste de (lat,lon[,time]) ou Point)."""
    a = Activity(
        id=aid, athleteId=athlete_id,
        athleteName=athlete_name or f"Ath {athlete_id}",
        type=atype, date=date, withAthletes=with_athletes or [],
    )
    track = []
    for p in points:
        track.append(p if isinstance(p, Point) else Point(*p))
    a.track = track
    return a


# --- Géométrie : offsets en mètres -> degrés ---
def lat_offset(meters):
    return meters / 110540.0


def lon_offset(lat, meters):
    return meters / (111320.0 * math.cos(math.radians(lat)))


def write_gpx(path, points):
    """Écrit un GPX minimal à partir de (lat, lon, datetime|None)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0"?>\n<gpx version="1.1" '
                'xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>\n')
        for la, lo, t in points:
            tt = (f"<time>{t.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
                  if t else "")
            f.write(f'<trkpt lat="{la}" lon="{lo}">{tt}</trkpt>\n')
        f.write('</trkseg></trk></gpx>\n')
