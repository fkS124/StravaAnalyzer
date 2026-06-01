"""
heatmap.py - Classe Heatmap du diagramme.
Génère une heatmap folium à partir de TOUS les points de TOUTES les traces.
"""
import folium
from folium.plugins import HeatMap


class Heatmap:
    """
    Diagramme :
        - densityMap : Map
        + generateDensityMap(activities)
    """

    def __init__(self):
        self.densityMap = None

    def generateDensityMap(self, activities):
        # On agrège tous les points de toutes les traces
        coords = []
        for a in activities:
            for p in a.track:
                coords.append([p.latitude, p.longitude])

        if not coords:
            self.densityMap = folium.Map(location=[48.8566, 2.3522], zoom_start=5)
            return self.densityMap

        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13,
                       tiles="OpenStreetMap", control_scale=True)
        HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
        self.densityMap = m
        return m
