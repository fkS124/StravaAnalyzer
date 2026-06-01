"""Tests unitaires : sort_manager.py."""
import unittest
from datetime import datetime

from sort_manager import SortManager
from tests._fixtures import mk_activity


class TestSortManager(unittest.TestCase):
    def setUp(self):
        self.sm = SortManager()

    def test_sort_by_activity_count(self):
        acts = [
            mk_activity("A", "U1", [(1, 1)]),
            mk_activity("B", "U1", [(1, 1)]),
            mk_activity("C", "U2", [(1, 1)]),
        ]
        ranking = self.sm.sortByActivityCount(acts)
        self.assertEqual(ranking[0], ("U1", 2))
        self.assertEqual(ranking[1], ("U2", 1))

    def test_sort_by_duration_from_timestamps(self):
        t0 = datetime(2025, 1, 1, 8, 0, 0)
        t1 = datetime(2025, 1, 1, 8, 30, 0)   # 1800 s
        long = mk_activity("A", "U1", [(1, 1, t0), (1, 1, t1)])
        short = mk_activity("B", "U2", [(1, 1, t0),
                                        (1, 1, datetime(2025, 1, 1, 8, 5, 0))])  # 300 s
        ranking = self.sm.sortByTotalDuration([short, long])
        self.assertEqual(ranking[0], ("U1", 1800))
        self.assertEqual(ranking[1], ("U2", 300))

    def test_duration_zero_when_no_timestamps(self):
        a = mk_activity("A", "U1", [(1, 1), (2, 2)])  # pas de time
        self.assertEqual(self.sm.sortByTotalDuration([a]), [("U1", 0)])


if __name__ == "__main__":
    unittest.main()
