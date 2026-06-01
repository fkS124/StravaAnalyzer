"""
Package de tests. Ajoute le dossier `app/` (modules à plat : models, app, …)
au sys.path pour que les tests fonctionnent aussi bien en local qu'en conteneur
(où app/ et tests/ sont des dossiers frères).
"""
import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
