"""Tests unitaires : file_manager.py (importCSV, exportResults)."""
import csv
import os
import tempfile
import unittest
from datetime import datetime

from file_manager import FileManager
from models import Intersection, Point
from tests._fixtures import write_gpx


CSV_HEADER = ("activity_id,athlete_name,activity_type,activity_date,athlete_id,"
              "activity_name,activity_location,activity_kudoers,"
              "activity_description,with_athletes\n")


class TestImportCSV(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.gpx = os.path.join(self.dir, "GPX")
        os.makedirs(self.gpx)
        self.csv = os.path.join(self.dir, "data.csv")

    def _write_csv(self, rows):
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write(CSV_HEADER)
            f.write("\n".join(rows) + "\n")

    def test_loads_activity_with_track(self):
        self._write_csv([
            "A001,Alice,Run,2024-06-01T08:00:00,U1,Run,Paris,5,desc,",
        ])
        write_gpx(os.path.join(self.gpx, "A001.gpx"),
                  [(45.0, 4.0, datetime(2024, 6, 1, 8, 0, 0))])
        acts = FileManager(gpx_dir=self.gpx).importCSV(self.csv)
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0].id, "A001")
        self.assertEqual(len(acts[0].track), 1)

    def test_activity_without_gpx_is_ignored(self):
        self._write_csv([
            "A001,Alice,Run,2024-06-01T08:00:00,U1,Run,Paris,5,desc,",
            "A002,Bob,Ride,2024-06-02T08:00:00,U2,Ride,Paris,5,desc,",
        ])
        write_gpx(os.path.join(self.gpx, "A001.gpx"), [(45.0, 4.0, None)])
        acts = FileManager(gpx_dir=self.gpx).importCSV(self.csv)
        self.assertEqual([a.id for a in acts], ["A001"])  # A002 ignorée

    def test_description_with_commas(self):
        self._write_csv([
            'A001,Alice,Run,2024-06-01T08:00:00,U1,Run,Paris,5,"Chaud, soleil",',
        ])
        write_gpx(os.path.join(self.gpx, "A001.gpx"), [(45.0, 4.0, None)])
        acts = FileManager(gpx_dir=self.gpx).importCSV(self.csv)
        self.assertEqual(acts[0].description, "Chaud, soleil")

    def test_missing_csv_returns_empty(self):
        acts = FileManager(gpx_dir=self.gpx).importCSV("/nope/missing.csv")
        self.assertEqual(acts, [])


class TestExportResults(unittest.TestCase):
    def test_export_intersections(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.csv")
            inter = [Intersection(datetime(2025, 1, 1, 9, 0, 0),
                                  Point(45.0, 4.0), ["U1", "U2"])]
            FileManager().exportResults(inter, out)
            with open(out, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["date", "latitude", "longitude", "userIds"])
            self.assertEqual(rows[1][3], "U1;U2")


if __name__ == "__main__":
    unittest.main()
