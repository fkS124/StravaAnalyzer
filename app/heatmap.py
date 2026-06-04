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
        self.densityMap = None # attribut qui stocke la carte générée (vide au départ)

    def generateDensityMap(self, activities): # méthode qui fait tout le travail
        # On parcourt toutes les activités, et pour chaque activité on parcourt tous les points de sa trace GPS.
        # On récupère la latitude et longitude de chaque point dans une liste coords
        coords = []
        for a in activities:
            for p in a.track:
                coords.append([p.latitude, p.longitude])
                
        # Si aucune activité n'a de trace, on retourne quand même une carte (centrée sur Paris par défaut).
        if not coords:
            self.densityMap = folium.Map(location=[48.8566, 2.3522], zoom_start=5)
            return self.densityMap

        # On fait la moyenne de toutes les latitudes et longitudes pour centrer la carte automatiquement sur la zone d'activité.
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)

        # folium.Map crée une carte interactive (style Google Maps)
        # HeatMap colorie les zones selon la densité de points : rouge là où tu passes souvent, bleu/vert là où tu passes peu
        # radius = taille de chaque point de chaleur, blur = flou entre les points, min_opacity = transparence minimale
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13,
                       tiles="OpenStreetMap", control_scale=True)
        HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
        self.densityMap = m
        return m
