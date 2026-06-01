"""
filter_manager.py - Classe FilterManager du diagramme.
Le filtrage par nom et par genre utilise les infos déjà présentes dans Activity
(athleteName), ou un mapping users_by_id (pour le genre, optionnel).
"""


class FilterManager:
    """
    Diagramme :
        + filterByName(activities, name) : List
        + filterByZone(activities, zone) : List
        + filterByGender(activities, gender) : List
        + filterByActivityType(activities, type) : List
    """

    def __init__(self, users_by_id=None):
        # users_by_id n'est utilisé que pour le filtre par genre (absent du CSV)
        self.users_by_id = users_by_id or {}

    def filterByName(self, activities, name):
        if not name:
            return list(activities)
        n = name.lower()
        return [a for a in activities if n in a.athleteName.lower()]

    def filterByZone(self, activities, zone):
        return zone.getActivitiesInZone(activities)

    def filterByGender(self, activities, gender):
        if not gender:
            return list(activities)
        g = gender.lower()
        return [
            a for a in activities
            if a.athleteId in self.users_by_id
            and self.users_by_id[a.athleteId].gender.lower() == g
        ]

    def filterByActivityType(self, activities, type):
        if not type:
            return list(activities)
        return [a for a in activities if a.type.lower() == type.lower()]
