"""
wsgi.py - Point d'entrée WSGI pour la production (gunicorn).

Initialise le Analyzer à partir des variables d'environnement, puis expose
l'objet Flask `app` attendu par gunicorn :

    gunicorn --bind 0.0.0.0:5000 wsgi:app

Variables d'environnement reconnues :
    CSV_PATH        chemin du CSV d'activités        (défaut: data.csv)
    GPX_DIR         dossier des traces GPX           (défaut: <csv>/GPX)
    DEMO            "true" => bandeau données démo    (défaut: false)
    DATASET_LABEL   libellé affiché dans l'IHM        (défaut: "")
"""
import os

import app as appmod
from app import app  # objet Flask exposé à gunicorn
from app import Analyzer, _env_bool

csv_path = os.path.abspath(os.environ.get("CSV_PATH", "data.csv"))
gpx_env = os.environ.get("GPX_DIR")
gpx_dir = os.path.abspath(gpx_env) if gpx_env else None

# Initialise le singleton utilisé par les routes Flask (app.viz).
appmod.viz = Analyzer(
    csv_path,
    gpx_dir=gpx_dir,
    demo=_env_bool("DEMO"),
    dataset_label=os.environ.get("DATASET_LABEL", ""),
)
