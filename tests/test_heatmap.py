"""Tests unitaires : heatmap.py."""
import unittest

import folium

from heatmap import Heatmap
from tests._fixtures import mk_activity


class TestHeatmap(unittest.TestCase):
    def test_generate_with_activities(self):
        acts = [mk_activity("A", "U1", [(45.0, 4.0), (45.1, 4.1)])]
        m = Heatmap().generateDensityMap(acts)
        self.assertIsInstance(m, folium.Map)

    def test_generate_empty_still_returns_map(self):
        m = Heatmap().generateDensityMap([])
        self.assertIsInstance(m, folium.Map)

    def test_generate_with_empty_tracks(self):
        acts = [mk_activity("A", "U1", [])]
        m = Heatmap().generateDensityMap(acts)
        self.assertIsInstance(m, folium.Map)


if __name__ == "__main__":
    unittest.main()
