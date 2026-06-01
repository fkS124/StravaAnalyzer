"""Tests unitaires : search_engine.py (zones denses + intersections)."""
import unittest
from datetime import datetime, timedelta

from search_engine import SearchEngine
from models import Zone, Point
from tests._fixtures import mk_activity, lat_offset, lon_offset

LAT = 45.76   # latitude de Lyon : exerce la correction longitude (cos lat)
LON = 4.83
T0 = datetime(2025, 1, 20, 9, 0, 0)

def far_filler(seed):
    """Points de remplissage TRÈS éloignés et PROPRES à chaque trace (régions
    distinctes selon `seed`) afin de ne jamais créer de faux appariement."""
    base = LAT + 1.0 + seed   # ~111 km par unité de seed
    return [(base + i * 0.001, LON + 1.0) for i in range(12)]


def crossing_activity(aid, athlete, cross_point, far_seed=0.0):
    """Trace dont le PREMIER point (toujours conservé par le sous-échantillonnage)
    est le point de croisement, suivi de points lointains propres à la trace."""
    return mk_activity(aid, athlete, [cross_point] + far_filler(far_seed))


class TestDenseZones(unittest.TestCase):
    def setUp(self):
        self.se = SearchEngine()

    def test_three_activities_form_dense_zone(self):
        pt = (LAT, LON)
        acts = [
            mk_activity("A", "U1", [pt, (LAT + lat_offset(20), LON)]),
            mk_activity("B", "U2", [pt, (LAT, LON + lon_offset(LAT, 20))]),
            mk_activity("C", "U3", [pt]),
        ]
        zones = self.se.findDenseZones(acts)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].activityCount, 3)
        self.assertEqual(zones[0].userIds, ["U1", "U2", "U3"])

    def test_below_threshold_no_zone(self):
        pt = (LAT, LON)
        acts = [mk_activity("A", "U1", [pt]), mk_activity("B", "U2", [pt])]
        self.assertEqual(self.se.findDenseZones(acts), [])

    def test_empty(self):
        self.assertEqual(self.se.findDenseZones([]), [])


class TestIntersections(unittest.TestCase):
    def setUp(self):
        self.se = SearchEngine()

    def test_same_point_same_time(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT, LON, T0), far_seed=1.0)
        inter = self.se.detectIntersections([a1], [a2])
        self.assertEqual(len(inter), 1)
        self.assertEqual(sorted(inter[0].userIds), ["U1", "U2"])

    def test_outside_time_window(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT, LON, T0 + timedelta(minutes=6)), far_seed=1.0)
        self.assertEqual(self.se.detectIntersections([a1], [a2]), [])

    def test_within_time_window(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT, LON, T0 + timedelta(minutes=4)), far_seed=1.0)
        self.assertEqual(len(self.se.detectIntersections([a1], [a2])), 1)

    def test_east_west_within_50m_detected(self):
        """Régression : 40 m est-ouest à 45.76° doivent être détectés
        (correction de l'échelle longitude)."""
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT, LON + lon_offset(LAT, 40), T0), far_seed=1.0)
        self.assertEqual(len(self.se.detectIntersections([a1], [a2])), 1)

    def test_east_west_over_50m_not_detected(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT, LON + lon_offset(LAT, 70), T0), far_seed=1.0)
        self.assertEqual(self.se.detectIntersections([a1], [a2]), [])

    def test_same_athlete_excluded(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U1", (LAT, LON, T0), far_seed=1.0)  # même athleteId
        self.assertEqual(self.se.detectIntersections([a1], [a2]), [])

    def test_empty_groups(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        self.assertEqual(self.se.detectIntersections([a1], []), [])
        self.assertEqual(self.se.detectIntersections([], [a1]), [])

    def test_one_intersection_per_pair(self):
        # a1 croise a2 en DEUX endroits -> une seule intersection retenue (dédup).
        cross2 = (LAT + lat_offset(300), LON, T0 + timedelta(minutes=1))
        a1 = mk_activity("A", "U1", [(LAT, LON, T0)] + far_filler(0) + [cross2])
        a2 = mk_activity("B", "U2", [(LAT, LON, T0)] + far_filler(1) + [cross2])
        self.assertEqual(len(self.se.detectIntersections([a1], [a2])), 1)

    def test_midpoint_location_between(self):
        a1 = crossing_activity("A", "U1", (LAT, LON, T0))
        a2 = crossing_activity("B", "U2", (LAT + lat_offset(30), LON, T0), far_seed=1.0)
        loc = self.se.detectIntersections([a1], [a2])[0].location
        self.assertTrue(LAT <= loc.latitude <= LAT + lat_offset(30))


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.se = SearchEngine()

    def test_filter_by_time(self):
        a = mk_activity("A", "U1", [(1, 1)], date=datetime(2025, 1, 10))
        b = mk_activity("B", "U2", [(1, 1)], date=datetime(2025, 2, 10))
        res = self.se.filterByTime([a, b], datetime(2025, 1, 1), datetime(2025, 1, 31))
        self.assertEqual([x.id for x in res], ["A"])

    def test_filter_by_location(self):
        z = Zone(Point(46, 3), Point(45, 5))
        a = mk_activity("A", "U1", [(45.5, 4.0)])
        b = mk_activity("B", "U2", [(40.0, 4.0)])
        self.assertEqual([x.id for x in self.se.filterByLocation([a, b], z)], ["A"])


if __name__ == "__main__":
    unittest.main()
