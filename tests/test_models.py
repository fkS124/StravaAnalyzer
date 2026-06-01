"""Tests unitaires : models.py (Point, Activity, Zone, DenseZone, helpers)."""
import os
import tempfile
import unittest
from datetime import datetime

from models import (Activity, Point, Zone, DenseZone, haversine_km,
                    _parse_date, _parse_gpx)
from tests._fixtures import mk_activity, write_gpx


class TestParseDate(unittest.TestCase):
    def test_iso_formats(self):
        self.assertEqual(_parse_date("2024-06-01T08:00:00"),
                         datetime(2024, 6, 1, 8, 0, 0))
        self.assertEqual(_parse_date("2024-06-01 08:00:00"),
                         datetime(2024, 6, 1, 8, 0, 0))
        self.assertEqual(_parse_date("2024-06-01"), datetime(2024, 6, 1))

    def test_trailing_z(self):
        self.assertEqual(_parse_date("2025-01-13T09:00:52Z"),
                         datetime(2025, 1, 13, 9, 0, 52))

    def test_invalid_and_empty(self):
        self.assertIsNone(_parse_date(""))
        self.assertIsNone(_parse_date("pas une date"))


class TestActivityParse(unittest.TestCase):
    def _row(self, **kw):
        base = ["A001", "Alice", "Run", "2024-06-01T08:00:00", "U1",
                "Morning run", "Paris", "12", "desc", ""]
        return base

    def test_parse_valid(self):
        a = Activity.parseFromCSV(self._row())
        self.assertEqual(a.id, "A001")
        self.assertEqual(a.athleteId, "U1")
        self.assertEqual(a.athleteName, "Alice")
        self.assertEqual(a.type, "Run")
        self.assertEqual(a.kudoers, 12)
        self.assertEqual(a.date, datetime(2024, 6, 1, 8, 0, 0))

    def test_with_athletes_variants(self):
        for raw, expected in [
            ("", []),
            ("U2", ["U2"]),
            ("U2;U3", ["U2", "U3"]),
            ("[U2, U3]", ["U2", "U3"]),
            ("U2,U3", ["U2", "U3"]),
            ("['U2', 'U3']", ["U2", "U3"]),
        ]:
            row = ["A", "n", "Run", "2024-06-01", "U1", "x", "Paris", "0", "", raw]
            a = Activity.parseFromCSV(row)
            self.assertEqual(a.withAthletes, expected, msg=raw)

    def test_short_row_returns_none(self):
        self.assertIsNone(Activity.parseFromCSV(["too", "short"]))

    def test_bad_kudos_defaults_zero(self):
        row = ["A", "n", "Run", "2024-06-01", "U1", "x", "Paris", "N/A", "", ""]
        self.assertEqual(Activity.parseFromCSV(row).kudoers, 0)


class TestActivityGeometry(unittest.TestCase):
    def test_coordinates_empty(self):
        a = mk_activity("A", "U1", [])
        self.assertEqual(a.getCoordinates().to_tuple(), (0.0, 0.0))

    def test_coordinates_first_point(self):
        a = mk_activity("A", "U1", [(1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(a.getCoordinates().to_tuple(), (1.0, 2.0))

    def test_centroid(self):
        a = mk_activity("A", "U1", [(0.0, 0.0), (2.0, 4.0)])
        c = a.getCentroid()
        self.assertAlmostEqual(c.latitude, 1.0)
        self.assertAlmostEqual(c.longitude, 2.0)

    def test_to_dict(self):
        a = mk_activity("A", "U1", [(1.0, 2.0)], date=datetime(2024, 1, 1))
        d = a.to_dict()
        self.assertEqual(d["id"], "A")
        self.assertEqual(d["trackLength"], 1)
        self.assertEqual(d["centroid"], [1.0, 2.0])


class TestParseGpx(unittest.TestCase):
    def test_parse_gpx_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.gpx")
            write_gpx(p, [(45.0, 4.0, datetime(2025, 1, 1, 8, 0, 0)),
                          (45.1, 4.1, datetime(2025, 1, 1, 8, 5, 0))])
            pts = _parse_gpx(p)
            self.assertEqual(len(pts), 2)
            self.assertAlmostEqual(pts[0].latitude, 45.0)
            self.assertEqual(pts[0].time, datetime(2025, 1, 1, 8, 0, 0))

    def test_missing_file(self):
        self.assertEqual(_parse_gpx("/nope/does_not_exist.gpx"), [])


class TestZone(unittest.TestCase):
    def test_contains_order_independent(self):
        z = Zone(Point(48.9, 2.2), Point(48.8, 2.4))  # topLeft/bottomRight
        self.assertTrue(z.contains(Point(48.85, 2.3)))
        self.assertFalse(z.contains(Point(48.95, 2.3)))

    def test_get_activities_in_zone_single_point(self):
        z = Zone(Point(1.0, 1.0), Point(0.0, 0.0))
        inside = mk_activity("A", "U1", [(5.0, 5.0), (0.5, 0.5)])  # 1 pt dans
        outside = mk_activity("B", "U2", [(5.0, 5.0), (6.0, 6.0)])
        res = z.getActivitiesInZone([inside, outside])
        self.assertEqual([a.id for a in res], ["A"])


class TestHaversine(unittest.TestCase):
    def test_same_point(self):
        self.assertAlmostEqual(haversine_km(Point(45, 4), Point(45, 4)), 0.0)

    def test_known_distance(self):
        # ~111 km pour 1° de latitude
        d = haversine_km(Point(45.0, 4.0), Point(46.0, 4.0))
        self.assertAlmostEqual(d, 111.19, delta=0.5)


class TestDenseZone(unittest.TestCase):
    def test_calculate_density(self):
        c = Point(45.0, 4.0)
        a1 = mk_activity("A", "U1", [(45.0001, 4.0001)])      # tout proche
        a2 = mk_activity("B", "U2", [(45.0002, 4.0)])         # proche
        far = mk_activity("C", "U3", [(46.0, 5.0)])           # loin
        z = DenseZone(center=c, radiusKm=0.3, activities=[a1, a2, far])
        self.assertEqual(z.activityCount, 2)
        self.assertEqual(z.userIds, ["U1", "U2"])


if __name__ == "__main__":
    unittest.main()
