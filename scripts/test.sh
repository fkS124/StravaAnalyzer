#!/usr/bin/env bash
# Lance toute la suite de tests (unitaires + intégration).
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/app${PYTHONPATH:+:$PYTHONPATH}"
exec python -m unittest discover -t . -s tests -p "test_*.py" -v
