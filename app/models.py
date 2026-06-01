"""
models.py - Classes de données du diagramme UML.
Contient : Point, User, Activity, Zone, DenseZone, Intersection
"""
from datetime import datetime
import math


class Point:
    """Point géographique (latitude, longitude), avec timestamp optionnel."""
    def __init__(self, latitude, longitude, time=None):
        self.latitude = latitude
        self.longitude = longitude
        self.time = time  # datetime ou None

    def to_tuple(self):
        return (self.latitude, self.longitude)


class Activity:
    """
    Diagramme adapté :
        - id, athleteId, athleteName, name, type, date, location
        - kudoers, description, withAthletes
        - track : List[Point]    <-- la trace GPX remplace latitude/longitude scalaires
        + parseFromCSV(csvFields) : Activity
        + loadTrack(gpxPath) : void
        + getCoordinates() : Point       (premier point de la trace)
        + getCentroid()   : Point        (barycentre de la trace)
    """
    def __init__(self, id, athleteId, athleteName, type, date, name="",
                 location="", kudoers=0, description="", withAthletes=None):
        self.id = id
        self.athleteId = athleteId
        self.athleteName = athleteName
        self.type = type
        self.date = date
        self.name = name
        self.location = location
        self.kudoers = kudoers
        self.description = description
        self.withAthletes = withAthletes or []  # liste d'athleteIds croisés
        self.track = []  # List[Point] -- rempli par loadTrack()

    # --- rétro-compatibilité (le diagramme prévoit userId / getCoordinates) ---
    @property
    def userId(self):
        """Alias pour athleteId (le diagramme parle de userId)."""
        return self.athleteId

    def getCoordinates(self):
        """Renvoie le premier point de la trace (ou Point(0,0) si trace vide)."""
        if self.track:
            return self.track[0]
        return Point(0.0, 0.0)

    def getCentroid(self):
        """Barycentre de la trace - utile pour positionner un marqueur."""
        if not self.track:
            return Point(0.0, 0.0)
        lat = sum(p.latitude for p in self.track) / len(self.track)
        lon = sum(p.longitude for p in self.track) / len(self.track)
        return Point(lat, lon)

    # ------------------------------------------------------------------
    @staticmethod
    def parseFromCSV(csvFields):
        """
        Construit une Activity depuis une LISTE de champs CSV (déjà parsée),
        car le CSV peut contenir des virgules dans certaines colonnes
        (description, with_athletes) -> on utilise csv.reader en amont.

        Format attendu :
            activity_id, athlete_name, activity_type, activity_date,
            athlete_id, activity_name, activity_location, activity_kudoers,
            activity_description, with_athletes
        """
        try:
            if len(csvFields) < 10:
                return None
            # with_athletes peut être : "" / "U2;U3" / "[U2, U3]" / "U2,U3"
            wa_raw = csvFields[9].strip().strip("[]")
            with_athletes = [
                x.strip().strip("'\"")
                for x in wa_raw.replace(";", ",").split(",")
                if x.strip()
            ]
            date = _parse_date(csvFields[3].strip())
            kudo_raw = csvFields[7].strip()
            kudoers = int(kudo_raw) if kudo_raw.lstrip("-").isdigit() else 0

            return Activity(
                id=csvFields[0].strip(),
                athleteName=csvFields[1].strip(),
                type=csvFields[2].strip(),
                date=date,
                athleteId=csvFields[4].strip(),
                name=csvFields[5].strip(),
                location=csvFields[6].strip(),
                kudoers=kudoers,
                description=csvFields[8].strip(),
                withAthletes=with_athletes,
            )
        except (ValueError, IndexError):
            return None

    def loadTrack(self, gpxPath):
        """Charge la trace GPX et remplit self.track."""
        self.track = _parse_gpx(gpxPath)
        return self.track

    def to_dict(self):
        c = self.getCentroid()
        return {
            "id": self.id,
            "athleteId": self.athleteId,
            "athleteName": self.athleteName,
            "type": self.type,
            "date": self.date.isoformat() if self.date else "",
            "name": self.name,
            "location": self.location,
            "kudoers": self.kudoers,
            "description": self.description,
            "withAthletes": self.withAthletes,
            "centroid": [c.latitude, c.longitude],
            "trackLength": len(self.track),
        }


# ----------------------------------------------------------------------
# Helpers : dates et GPX
# ----------------------------------------------------------------------
def _parse_date(raw):
    """Essaye plusieurs formats classiques de date Strava."""
    if not raw:
        return None
    fmts = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%b %d, %Y, %I:%M:%S %p",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d",
    ]
    for f in fmts:
        try:
            return datetime.strptime(raw, f)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", ""))
    except ValueError:
        return None


def _parse_gpx(gpxPath):
    """
    Parse un fichier GPX et retourne une liste de Points.
    Format GPX standard : <trkpt lat="..." lon="..."><time>...</time></trkpt>
    Implémentation indépendante (xml.etree de la stdlib).
    """
    import xml.etree.ElementTree as ET
    points = []
    try:
        tree = ET.parse(gpxPath)
        root = tree.getroot()
        # Le GPX déclare un namespace par défaut -> on l'extrait
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        # On cherche d'abord les points de trace, puis les points de route, puis les waypoints
        for tag in ("trkpt", "rtept", "wpt"):
            for el in root.iter(ns + tag):
                try:
                    lat = float(el.attrib["lat"])
                    lon = float(el.attrib["lon"])
                    t_el = el.find(ns + "time")
                    time = _parse_date(t_el.text) if t_el is not None else None
                    points.append(Point(lat, lon, time))
                except (KeyError, ValueError):
                    continue
            if points:
                break
    except (ET.ParseError, FileNotFoundError, OSError):
        pass
    return points


# ----------------------------------------------------------------------
# User
# ----------------------------------------------------------------------
class User:
    """
    Diagramme :
        - id, name, gender
        + activities : List
        + getUserActivities() : List
    NB : les utilisateurs sont désormais déduits du CSV (athlete_id/name).
    Le genre n'est plus dans le CSV donné -> reste vide par défaut.
    """
    def __init__(self, id, name, gender=""):
        self.id = id
        self.name = name
        self.gender = gender
        self.activities = []

    def getUserActivities(self):
        return self.activities


# ----------------------------------------------------------------------
# Zone, DenseZone, Intersection
# ----------------------------------------------------------------------
class Zone:
    """
    Diagramme :
        - topLeft, bottomRight : Point
        + contains(point) : bool
        + getActivitiesInZone(activities) : List
    Une activité est dans la zone si AU MOINS UN point de sa trace y est.
    """
    def __init__(self, topLeft, bottomRight):
        self.topLeft = topLeft
        self.bottomRight = bottomRight

    def contains(self, point):
        lat_max = max(self.topLeft.latitude, self.bottomRight.latitude)
        lat_min = min(self.topLeft.latitude, self.bottomRight.latitude)
        lon_max = max(self.topLeft.longitude, self.bottomRight.longitude)
        lon_min = min(self.topLeft.longitude, self.bottomRight.longitude)
        return lat_min <= point.latitude <= lat_max and lon_min <= point.longitude <= lon_max

    def getActivitiesInZone(self, activities):
        return [a for a in activities
                if any(self.contains(p) for p in a.track)]


def haversine_km(p1, p2):
    """Distance haversine en km entre deux Points."""
    R = 6371.0
    lat1, lon1 = math.radians(p1.latitude), math.radians(p1.longitude)
    lat2, lon2 = math.radians(p2.latitude), math.radians(p2.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


class DenseZone:
    """
    Diagramme :
        - center : Point
        - radiusKm : double
        - activityCount : int
        - userIds : List
        + calculateDensity() : void
    """
    def __init__(self, center, radiusKm, activities=None):
        self.center = center
        self.radiusKm = radiusKm
        self.activityCount = 0
        self.userIds = []
        self._activities = activities or []
        if self._activities:
            self.calculateDensity()

    def calculateDensity(self):
        """Une activité compte si au moins un point de sa trace est dans le cercle."""
        in_zone = []
        for a in self._activities:
            for p in a.track:
                if haversine_km(self.center, p) <= self.radiusKm:
                    in_zone.append(a)
                    break
        self.activityCount = len(in_zone)
        self.userIds = sorted({a.athleteId for a in in_zone})


class Intersection:
    """
    Diagramme :
        - date : LocalDateTime
        - location : Point
        - userIds : List
        + getDate(), getLocation(), getUserIds()
    """
    def __init__(self, date, location, userIds):
        self.date = date
        self.location = location
        self.userIds = list(userIds)

    def getDate(self):
        return self.date

    def getLocation(self):
        return self.location

    def getUserIds(self):
        return self.userIds
