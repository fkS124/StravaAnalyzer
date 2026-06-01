# syntax=docker/dockerfile:1
# ----------------------------------------------------------------------
# Strava Analyzer - image de production
# Les tests (unitaires + intégration) sont exécutés au démarrage AVANT le
# serveur (cf. entrypoint.sh) : si un test échoue, le serveur ne démarre pas.
# ----------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# 1) Dépendances (couche cache séparée du code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Code applicatif + tests (dossiers frères, comme dans le dépôt)
COPY app/   /srv/app/
COPY tests/ /srv/tests/
COPY entrypoint.sh /srv/entrypoint.sh

# 3) Données : par défaut on embarque le jeu de DÉMONSTRATION fictif.
#    (les données réelles restent montables via un volume, cf. docker-compose)
COPY data/ /data/

RUN chmod +x /srv/entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /srv /data
USER appuser

# Configuration par défaut : jeu de démonstration, bandeau activé.
ENV PYTHONPATH=/srv/app \
    APP_ROOT=/srv \
    HOST=0.0.0.0 \
    PORT=5000 \
    CSV_PATH=/data/demo/data.csv \
    GPX_DIR=/data/demo/GPX \
    DEMO=true \
    DATASET_LABEL="Jeu de démonstration — Lyon" \
    NO_BROWSER=true

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=4s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','5000')+'/api/meta').read()" || exit 1

# entrypoint = tests puis exec de la commande ; CMD = serveur WSGI de production.
ENTRYPOINT ["/srv/entrypoint.sh"]
CMD ["gunicorn", "--chdir", "/srv/app", "--bind", "0.0.0.0:5000", \
     "--workers", "1", "--threads", "4", "--timeout", "120", "wsgi:app"]
