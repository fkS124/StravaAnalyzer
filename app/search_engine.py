"""
search_engine.py - Classe SearchEngine du diagramme.

Les traces GPX changent la logique :
  - findDenseZones agrège TOUS les points de TOUTES les traces sur une grille
    et compte combien d'activités distinctes traversent chaque cellule.
  - detectIntersections compare les points des deux groupes de traces entre eux
    (proximité spatiale + proximité temporelle).

Note géométrique : un degré de latitude vaut ~111 km partout, mais un degré de
longitude vaut 111*cos(latitude) km. On corrige donc la taille des cellules en
longitude par cos(lat_ref), sinon, aux latitudes européennes (~45°), une
cellule "carrée en degrés" est ~1,4× trop petite en est-ouest et le voisinage
3×3 peut rater des points pourtant proches sur le terrain.
"""
import math
from collections import defaultdict
from datetime import timedelta

from models import Point, DenseZone, Intersection, haversine_km


def _cell_sizes(km, ref_lat):
    """Taille de cellule (deg) en lat et lon pour une maille de `km` kilomètres."""
    lat_deg = km / 111.0
    cos = math.cos(math.radians(ref_lat)) or 1e-6
    lon_deg = km / (111.0 * cos)
    return lat_deg, lon_deg


def _mean_lat(*groups):
    """Latitude moyenne de tous les points (référence pour l'échelle longitude)."""
    s, n = 0.0, 0
    for g in groups:
        for a in g:
            for p in a.track:
                s += p.latitude
                n += 1
    return (s / n) if n else 0.0


class SearchEngine:
    """
    Diagramme :
        + filterByLocation(activities, zone) : List
        + filterByTime(activities, start, end) : List
        + findDenseZones(activities) : List
        + detectIntersections(activities1, activities2) : List
    """

    DENSE_ZONE_RADIUS_KM = 0.3
    MIN_ACTIVITIES_FOR_DENSE = 3
    INTERSECTION_TIME_WINDOW_MIN = 5
    INTERSECTION_DISTANCE_M = 50
    # On sous-échantillonne les traces lourdes pour rester rapide
    TRACK_DOWNSAMPLE = 10  # garde 1 point sur N

    def filterByLocation(self, activities, zone):
        return zone.getActivitiesInZone(activities)

    def filterByTime(self, activities, start, end):
        return [a for a in activities if a.date and start <= a.date <= end]

    # ------------------------------------------------------------------
    def findDenseZones(self, activities):
        """
        Agrège les points de toutes les activités sur une grille et identifie les
        cellules traversées par au moins MIN_ACTIVITIES_FOR_DENSE activités distinctes.

        Les cellules denses sont ensuite regroupées en clusters via un flood-fill :
        chaque cellule dense est d'abord étendue de MERGE_GAP cellules dans toutes les
        directions, puis les zones élargies qui se touchent sont fusionnées en un seul
        cluster. Seules les données des cellules originellement denses contribuent au
        centre et aux compteurs du résultat — MERGE_GAP sert uniquement à décider si
        deux zones doivent être fusionnées, pas à dilater la zone retournée.

        Retourne une liste de DenseZone triée par activityCount décroissant.
        """
        if not activities:
            return []
        lat_cell, lon_cell = _cell_sizes(self.DENSE_ZONE_RADIUS_KM,
                                         _mean_lat(activities))
        cell_to_acts = defaultdict(set)
        cell_to_points = defaultdict(list)
        cell_to_users = defaultdict(set)

        for a in activities:
            seen_cells = set()
            for p in a.track[::self.TRACK_DOWNSAMPLE]:
                key = (round(p.latitude / lat_cell),
                       round(p.longitude / lon_cell))
                seen_cells.add(key)
                cell_to_points[key].append(p)
            for key in seen_cells:
                cell_to_acts[key].add(a.id)
                cell_to_users[key].add(a.athleteId)

        dense_cells = {
            key for key, act_ids in cell_to_acts.items()
            if len(act_ids) >= self.MIN_ACTIVITIES_FOR_DENSE
        }

        # Flood-fill sur les cellules denses élargies de MERGE_GAP,
        # mais on n'agrège que les données des cellules originellement denses.
        MERGE_GAP = 1
        expanded = {
            (cx + dx, cy + dy)
            for (cx, cy) in dense_cells
            for dx in range(-MERGE_GAP, MERGE_GAP + 1)
            for dy in range(-MERGE_GAP, MERGE_GAP + 1)
        }

        visited = set()
        zones = []

        for start in dense_cells:
            if start in visited:
                continue
            # BFS dans l'espace élargi
            cluster_dense = set()
            queue = [start]
            visited.add(start)
            while queue:
                cx, cy = queue.pop()
                if (cx, cy) in dense_cells:
                    cluster_dense.add((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nb = (cx + dx, cy + dy)
                        if nb not in visited and nb in expanded:
                            visited.add(nb)
                            queue.append(nb)

            # Calcul identique à l'original, mais sur tout le cluster
            all_act_ids = set()
            all_user_ids = set()
            all_pts = []
            for key in cluster_dense:
                all_act_ids |= cell_to_acts[key]
                all_user_ids |= cell_to_users[key]
                all_pts.extend(cell_to_points[key])

            avg_lat = sum(p.latitude for p in all_pts) / len(all_pts)
            avg_lon = sum(p.longitude for p in all_pts) / len(all_pts)
            z = DenseZone(
                center=Point(avg_lat, avg_lon),
                radiusKm=self.DENSE_ZONE_RADIUS_KM,
            )
            z.activityCount = len(all_act_ids)
            z.userIds = sorted(all_user_ids)
            zones.append(z)

        zones.sort(key=lambda z: z.activityCount, reverse=True)
        return zones

    # ------------------------------------------------------------------
    def detectIntersections(self, activities1, activities2):
        """
        Compare TOUS les points des traces du groupe 1 contre TOUS les points
        des traces du groupe 2. Une intersection est créée quand un point de
        chaque côté est proche en espace (<= INTERSECTION_DISTANCE_M m) ET en
        temps (<= INTERSECTION_TIME_WINDOW_MIN minutes).

        Pour éviter la combinatoire, on indexe le groupe 2 sur une grille dont
        la maille vaut exactement INTERSECTION_DISTANCE_M (corrigée en
        longitude). On inspecte alors les 9 cellules autour de chaque point du
        groupe 1, ce qui couvre tout point situé à <= INTERSECTION_DISTANCE_M.
        Un seul point d'intersection est retenu par couple (activity1, activity2).
        """
        if not activities1 or not activities2:
            return []

        km = self.INTERSECTION_DISTANCE_M / 1000.0
        lat_cell, lon_cell = _cell_sizes(km, _mean_lat(activities1, activities2))

        # Index spatial du groupe 2 : cell -> [(act_idx, point)]
        index = defaultdict(list)
        for j, a2 in enumerate(activities2):
            for p in a2.track[::self.TRACK_DOWNSAMPLE]:
                key = (round(p.latitude / lat_cell),
                       round(p.longitude / lon_cell))
                index[key].append((j, p))

        time_window = timedelta(minutes=self.INTERSECTION_TIME_WINDOW_MIN)
        intersections = []
        seen_pairs = set()

        for a1 in activities1:
            for p1 in a1.track[::self.TRACK_DOWNSAMPLE]:
                cx = round(p1.latitude / lat_cell)
                cy = round(p1.longitude / lon_cell)
                # On inspecte les 9 cellules autour
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        bucket = index.get((cx + dx, cy + dy))
                        if not bucket:
                            continue
                        for (j, p2) in bucket:
                            a2 = activities2[j]
                            if a1.athleteId == a2.athleteId:
                                continue
                            pair_key = (a1.id, a2.id)
                            if pair_key in seen_pairs:
                                continue
                            # Test temporel : on a besoin des timestamps des
                            # points. À défaut, on retombe sur la date globale
                            # de l'activité.
                            t1 = p1.time or a1.date
                            t2 = p2.time or a2.date
                            if t1 and t2 and abs(t1 - t2) > time_window:
                                continue
                            # Test spatial précis (haversine en m)
                            d_m = haversine_km(p1, p2) * 1000
                            if d_m > self.INTERSECTION_DISTANCE_M:
                                continue
                            mid = Point((p1.latitude + p2.latitude) / 2,
                                        (p1.longitude + p2.longitude) / 2)
                            mid_date = t1 if (t1 and t2 is None) else (
                                t1 + (t2 - t1) / 2 if (t1 and t2) else None
                            )
                            intersections.append(Intersection(
                                date=mid_date, location=mid,
                                userIds=[a1.athleteId, a2.athleteId],
                            ))
                            seen_pairs.add(pair_key)
        return intersections
