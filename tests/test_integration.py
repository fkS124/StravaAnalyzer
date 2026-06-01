"""
Tests d'intégration : le serveur Flask et tous ses endpoints /api/*, en passant
par le pipeline complet (FileManager -> filtres -> SearchEngine -> JSON).

On construit un petit jeu de données réel (CSV + GPX sur disque), on charge un
Analyzer et on interroge l'application via son test_client (aucun réseau).
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime

import app as appmod
from app import Analyzer
from tests._fixtures import write_gpx

LAT, LON = 45.76, 4.83
T0 = datetime(2025, 1, 20, 9, 0, 0)
T10 = datetime(2025, 1, 20, 9, 10, 0)

CSV_HEADER = ("activity_id,athlete_name,activity_type,activity_date,athlete_id,"
              "activity_name,activity_location,activity_kudoers,"
              "activity_description,with_athletes\n")


class IntegrationBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        gpx = os.path.join(cls.dir, "GPX")
        os.makedirs(gpx)
        csv_path = os.path.join(cls.dir, "data.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(CSV_HEADER)
            f.write("A1,Alice,Run,2025-01-20T09:00:00,U1,Run matin,Lyon,5,,\n")
            f.write("A2,Bob,Ride,2025-01-20T09:00:00,U2,Vélo,Lyon,3,,\n")
            f.write("A3,Carol,Run,2025-01-20T09:00:00,U3,Footing,Lyon,1,,\n")
        # A1 & A2 & A3 passent par le MÊME point P0 à T0 -> zone dense + intersections
        write_gpx(os.path.join(gpx, "A1.gpx"),
                  [(LAT, LON, T0), (LAT + 0.0001, LON, T10)])      # durée 600 s
        write_gpx(os.path.join(gpx, "A2.gpx"),
                  [(LAT, LON, T0), (45.80, 4.90, T0)])             # part loin ensuite
        write_gpx(os.path.join(gpx, "A3.gpx"), [(LAT, LON, T0)])

        appmod.viz = Analyzer(csv_path, gpx_dir=gpx, demo=True,
                                dataset_label="Fixture")
        appmod.app.config["TESTING"] = True
        cls.client = appmod.app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def get(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, path)
        return r.get_json()


class TestEndpoints(IntegrationBase):
    def test_meta(self):
        m = self.get("/api/meta")
        self.assertTrue(m["demo"])
        self.assertEqual(m["datasetLabel"], "Fixture")
        self.assertEqual(m["nbActivities"], 3)
        self.assertEqual(m["nbAthletes"], 3)

    def test_users_sorted(self):
        users = self.get("/api/users")
        self.assertEqual([u["name"] for u in users], ["Alice", "Bob", "Carol"])

    def test_types(self):
        self.assertEqual(self.get("/api/types"), ["Ride", "Run"])

    def test_heatmap(self):
        d = self.get("/api/heatmap")
        self.assertEqual(d["count"], 3)
        self.assertEqual(d["totalPoints"], 5)  # 2 + 2 + 1

    def test_tracks(self):
        tracks = self.get("/api/tracks")
        self.assertEqual(len(tracks), 3)
        self.assertIn("points", tracks[0])

    def test_activities_table(self):
        acts = self.get("/api/activities")
        self.assertEqual(len(acts), 3)
        self.assertIn("trackLength", acts[0])

    def test_dense_zones(self):
        zones = self.get("/api/dense_zones")
        self.assertGreaterEqual(len(zones), 1)
        self.assertGreaterEqual(zones[0]["count"], 3)

    def test_intersections(self):
        inter = self.get("/api/intersections?user1=U1&user2=U2")
        self.assertGreaterEqual(len(inter), 1)
        self.assertEqual(sorted(inter[0]["users"]), ["U1", "U2"])

    def test_intersections_missing_param(self):
        self.assertEqual(self.get("/api/intersections?user1=U1"), [])

    def test_sort_count(self):
        d = self.get("/api/sort?mode=count")
        self.assertEqual(len(d["ranking"]), 3)
        self.assertTrue(all(r["value"] == 1 for r in d["ranking"]))

    def test_sort_duration(self):
        d = self.get("/api/sort?mode=duration")
        top = {r["userId"]: r["value"] for r in d["ranking"]}
        self.assertEqual(top["U1"], 600)   # A1 = 600 s


class TestFilterChaining(IntegrationBase):
    def test_filter_by_type(self):
        self.assertEqual(self.get("/api/heatmap?type=Run")["count"], 2)
        self.assertEqual(self.get("/api/heatmap?type=Ride")["count"], 1)

    def test_filter_by_name(self):
        self.assertEqual(self.get("/api/heatmap?name=alice")["count"], 1)

    def test_filter_by_zone(self):
        # zone autour de P0 (lat1,lon1,lat2,lon2) : ne contient pas (45.80,4.90)
        zone = "45.77,4.82,45.75,4.84"
        d = self.get(f"/api/heatmap?zone={zone}")
        self.assertEqual(d["count"], 3)  # les 3 ont un point dans la zone

    def test_filters_combined(self):
        d = self.get("/api/heatmap?type=Run&name=carol")
        self.assertEqual(d["count"], 1)


if __name__ == "__main__":
    unittest.main()
