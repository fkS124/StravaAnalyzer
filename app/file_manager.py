"""
file_manager.py - Classe FileManager du diagramme.

Importe les activités depuis :
  - un CSV de méta-données (colonnes : activity_id, athlete_name, activity_type,
    activity_date, athlete_id, activity_name, activity_location, activity_kudoers,
    activity_description, with_athletes)
  - un dossier GPX/ contenant un fichier `<activity_id>.gpx` par activité.

Exporte les intersections en CSV.
"""
import csv
import os
from models import Activity


class FileManager:
    """
    Diagramme :
        + importCSV(filePath) : List
        + exportResults(intersections, outputPath) : void
    """

    def __init__(self, gpx_dir=None):
        # Dossier contenant les .gpx (par défaut : ./GPX/ à côté du CSV)
        self.gpx_dir = gpx_dir

    def importCSV(self, filePath):
        """Lit le CSV et associe chaque activité à sa trace GPX."""
        activities = []
        gpx_dir = self.gpx_dir or os.path.join(
            os.path.dirname(os.path.abspath(filePath)), "GPX"
        )

        missing_gpx = 0
        try:
            with open(filePath, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # saute la ligne d'en-tête
                for row in reader:
                    if not row or all(not c.strip() for c in row):
                        continue
                    a = Activity.parseFromCSV(row)
                    if a is None:
                        continue
                    # Cherche le GPX correspondant : <id>.gpx ou <id>.GPX
                    gpx_path = self._find_gpx(gpx_dir, a.id)
                    if gpx_path:
                        a.loadTrack(gpx_path)
                    if not a.track:
                        missing_gpx += 1
                        continue  # on ignore les activités sans trace
                    activities.append(a)
        except FileNotFoundError:
            print(f"[FileManager] CSV introuvable : {filePath}")
            return []

        print(f"[FileManager] {len(activities)} activités chargées depuis {filePath}")
        if missing_gpx:
            print(f"[FileManager] {missing_gpx} activités ignorées (GPX manquant ou vide)")
        return activities

    @staticmethod
    def _find_gpx(gpx_dir, activity_id):
        """Cherche le fichier GPX en testant plusieurs extensions/casses."""
        if not os.path.isdir(gpx_dir):
            return None
        for ext in (".gpx", ".GPX", ".Gpx"):
            path = os.path.join(gpx_dir, f"{activity_id}{ext}")
            if os.path.isfile(path):
                return path
        return None

    def exportResults(self, intersections, outputPath):
        """Exporte une liste d'Intersections en CSV."""
        try:
            with open(outputPath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "latitude", "longitude", "userIds"])
                for inter in intersections:
                    writer.writerow([
                        inter.getDate().isoformat() if inter.getDate() else "",
                        inter.getLocation().latitude,
                        inter.getLocation().longitude,
                        ";".join(inter.getUserIds()),
                    ])
        except OSError as e:
            print(f"[FileManager] erreur d'écriture : {e}")
