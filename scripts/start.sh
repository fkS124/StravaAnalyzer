#!/usr/bin/env bash
# Démarrage LOCAL (sans Docker) : tests d'abord, puis serveur sur les données démo.
# Tout argument supplémentaire est transmis à app.py (ex: --port 8000).
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/app${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Tests (unitaires + intégration)..."
python -m unittest discover -t . -s tests -p "test_*.py"

echo "==> Tests OK — démarrage du serveur (données de démonstration)"
cd app
exec python app.py --csv ../data/demo/data.csv --gpx ../data/demo/GPX --demo \
     --dataset-label "Jeu de démonstration — Lyon" "$@"
