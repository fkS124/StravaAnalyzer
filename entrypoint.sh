#!/bin/sh
# Entrypoint conteneur : lance la suite de tests AVANT le serveur.
# Si un test échoue, `set -e` interrompt le script -> le serveur ne démarre pas.
set -e

ROOT="${APP_ROOT:-/srv}"
cd "$ROOT"

echo "=================================================="
echo "  Tests (unitaires + intégration) avant démarrage"
echo "=================================================="
python -m unittest discover -t . -s tests -p "test_*.py" -v

echo "=================================================="
echo "  Tests OK — démarrage du serveur"
echo "=================================================="
exec "$@"
