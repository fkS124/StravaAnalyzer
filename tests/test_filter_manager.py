"""Tests unitaires : filter_manager.py."""
import unittest

from filter_manager import FilterManager
from models import User, Zone, Point
from tests._fixtures import mk_activity


class TestFilterManager(unittest.TestCase):
    def setUp(self):
        self.alice = mk_activity("A", "U1", [(45.0, 4.0)], athlete_name="Alice Martin", atype="Run")
        self.bob = mk_activity("B", "U2", [(46.0, 5.0)], athlete_name="Bob Dupont", atype="Ride")
        self.acts = [self.alice, self.bob]
        self.fm = FilterManager()

    def test_filter_by_name_case_insensitive_substring(self):
        self.assertEqual([a.id for a in self.fm.filterByName(self.acts, "alice")], ["A"])
        self.assertEqual([a.id for a in self.fm.filterByName(self.acts, "DUP")], ["B"])

    def test_filter_by_name_empty_returns_all(self):
        self.assertEqual(len(self.fm.filterByName(self.acts, "")), 2)

    def test_filter_by_type_case_insensitive(self):
        self.assertEqual([a.id for a in self.fm.filterByActivityType(self.acts, "run")], ["A"])
        self.assertEqual([a.id for a in self.fm.filterByActivityType(self.acts, "RIDE")], ["B"])

    def test_filter_by_type_empty_returns_all(self):
        self.assertEqual(len(self.fm.filterByActivityType(self.acts, "")), 2)

    def test_filter_by_zone(self):
        z = Zone(Point(45.5, 3.5), Point(44.5, 4.5))  # contient (45,4)
        self.assertEqual([a.id for a in self.fm.filterByZone(self.acts, z)], ["A"])

    def test_filter_by_gender(self):
        users = {"U1": User("U1", "Alice", "F"), "U2": User("U2", "Bob", "M")}
        fm = FilterManager(users_by_id=users)
        self.assertEqual([a.id for a in fm.filterByGender(self.acts, "F")], ["A"])
        self.assertEqual(len(fm.filterByGender(self.acts, "")), 2)


if __name__ == "__main__":
    unittest.main()
