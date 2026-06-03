"""
heatmap.py - Classe Heatmap du diagramme.
Génère une heatmap folium à partir de TOUS les points de TOUTES les traces.
"""
import folium # bibliothèque Python pour créer des cartes interactives
from folium.plugins import HeatMap # plugin spécifique pour les cartes de chaleur


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
        coords = [] # liste vide qui va accumuler tous les points GPS
        for a in activities: # on parcourt chaque activité une par une
            for p in a.track: # pour chaque activité, on parcourt chaque point de sa trace
                coords.append([p.latitude, p.longitude]) # on ajoute [lat, lon] à la liste
                
        # Si aucune activité n'a de trace, on retourne quand même une carte (centrée sur Paris par défaut).
        if not coords: 
            self.densityMap = folium.Map(location=[48.8566, 2.3522], zoom_start=5)
            # on crée quand même une carte, centrée sur Paris, niveau de zoom 5 (vue Europe)
            return self.densityMap # on retourne cette carte vide et on s'arrête là

        # On fait la moyenne de toutes les latitudes et longitudes pour centrer la carte automatiquement sur la zone d'activité.
        avg_lat = sum(c[0] for c in coords) / len(coords)
        # on additionne toutes les latitudes  et on divise par le nombre de points → moyenne
        avg_lon = sum(c[1] for c in coords) / len(coords)
        # même chose pour les longitudes → on obtient le centre géographique de toutes les traces
        
        # folium.Map crée une carte interactive (style Google Maps)
        # HeatMap colorie les zones selon la densité de points : rouge là où tu passes souvent, bleu/vert là où tu passes peu
        # radius = taille de chaque point de chaleur, blur = flou entre les points, min_opacity = transparence minimale
        m = folium.Map(location=[avg_lat, avg_lon], # centre de la carte = moyenne calculée juste avant
                       zoom_start=13, # niveau de zoom 13 = vue quartier/ville
                       tiles="OpenStreetMap", # fond de carte style OpenStreetMap (gratuit, open source)
                       control_scale=True) # affiche une échelle (ex: "500m") en bas de la carte
        HeatMap(coords, radius=12, blur=15, min_opacity=0.4).add_to(m)
        self.densityMap = m
        return m
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
