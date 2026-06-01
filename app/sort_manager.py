"""
sort_manager.py - Classe SortManager du diagramme.
"""
from collections import defaultdict


def _track_duration_s(track):
    """Durée d'une trace en secondes, à partir des timestamps GPX."""
    times = [p.time for p in track if p.time is not None]
    if len(times) < 2:
        return 0
    return int((max(times) - min(times)).total_seconds())


class SortManager:
    """
    Diagramme :
        + sortByActivityCount(activities) : List
        + sortByTotalDuration(activities) : List

    On retourne une liste de tuples (athleteId, valeur) triée décroissante.
    """

    def sortByActivityCount(self, activities):
        counts = defaultdict(int)
        for a in activities:
            counts[a.athleteId] += 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)

    def sortByTotalDuration(self, activities):
        """Durée totale en secondes, dérivée des timestamps GPX."""
        totals = defaultdict(int)
        for a in activities:
            totals[a.athleteId] += _track_duration_s(a.track)
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)
