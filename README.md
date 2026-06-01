# Strava Analyzer

Application web (Flask + Leaflet) qui charge des activités Strava (CSV + traces
GPX) et affiche une **heatmap interactive** avec filtres, tri, détection de
**zones denses**, **intersections** entre athlètes et sélection de zone à la
souris.

> ⚠️ **Cette livraison démarre par défaut sur un jeu de DONNÉES DE
> DÉMONSTRATION 100 % FICTIVES.** Les athlètes sont nommés `[DÉMO] …`, les
> traces dessinent des **formes géométriques** (carré, triangle, cercle,
> étoile) et un **bandeau d'avertissement** s'affiche en haut de l'interface.
> Aucune personne réelle n'est concernée par ce jeu de démonstration.

---

## 1. Démarrage rapide (Docker)

Pré-requis : **Docker** + **Docker Compose** (inclus dans Docker Desktop).

```bash
# Jeu de DÉMONSTRATION (fictif) — recommandé pour une première découverte
docker compose up --build
```

Ouvrir ensuite **http://localhost:5000**.

Pour arrêter : `Ctrl-C` puis `docker compose down`.

### Lancer sur les données réelles

Les données réelles ne sont **pas** incluses dans l'image (pour des raisons de
confidentialité / RGPD) : elles sont montées depuis `data/real/` au démarrage.

```bash
docker compose --profile real up --build
# -> http://localhost:5001   (bandeau démo désactivé)
```

### Sans docker-compose (Docker seul)

```bash
docker build -t strava-analyzer .
docker run --rm -p 5000:5000 strava-analyzer            # démo
# données réelles montées en volume :
docker run --rm -p 5000:5000 \
  -e DEMO=false -e DATASET_LABEL="Données réelles" \
  -e CSV_PATH=/data/data.csv -e GPX_DIR=/data/GPX \
  -v "$(pwd)/data/real:/data:ro" strava-analyzer
```

---

## 2. Configuration (variables d'environnement)

| Variable        | Défaut (image)        | Rôle                                            |
|-----------------|-----------------------|-------------------------------------------------|
| `CSV_PATH`      | `/data/demo/data.csv` | CSV des métadonnées d'activités                 |
| `GPX_DIR`       | `/data/demo/GPX`      | Dossier des traces `<activity_id>.gpx`          |
| `DEMO`          | `true`                | Affiche le bandeau « données de démonstration » |
| `DATASET_LABEL` | `Jeu de démonstration`| Libellé affiché dans l'IHM                      |
| `HOST` / `PORT` | `0.0.0.0` / `5000`    | Interface et port d'écoute                      |

---

## 3. Format des données

**`data.csv`** (séparateur `,`, en-tête obligatoire) :

```
activity_id,athlete_name,activity_type,activity_date,athlete_id,
activity_name,activity_location,activity_kudoers,activity_description,with_athletes
```

- `activity_date` accepte plusieurs formats ISO.
- `with_athletes` accepte `""`, `"U2"`, `"U2;U3"`, `"[U2, U3]"`, `"U2,U3"`.
- Les champs contenant des virgules doivent être entre guillemets.

**Dossier `GPX/`** : un fichier `<activity_id>.gpx` par activité (format GPX
standard `<trkpt lat="…" lon="…"><time>…</time></trkpt>`). **Une activité sans
GPX correspondant est ignorée** au chargement.

---

## 4. Fonctionnalités de l'IHM

- **Heatmap** : agrège tous les points de toutes les traces filtrées.
- **Filtres** (cumulatifs) : nom d'athlète, type d'activité, zone dessinée à la
  souris (outil rectangle, en haut à droite de la carte).
- **Affichage des traces** : polylignes individuelles, une couleur par athlète.
- **Tri** : par nombre d'activités ou par durée totale (timestamps GPX).
- **Zones denses** : cellules traversées par ≥ 3 activités distinctes.
- **Intersections** : passages de deux athlètes au même endroit (~50 m) dans la
  même fenêtre temporelle (~5 min).
- **Tableau** des activités filtrées.

---

## 5. Tests (joués AVANT le démarrage du serveur)

La suite de tests valide chaque fonctionnalité (parsing CSV/GPX, filtres, tri,
zones denses, intersections, heatmap) et l'intégration des endpoints HTTP.

- **En Docker** : `entrypoint.sh` lance les tests à chaque démarrage du
  conteneur. **Si un test échoue, le serveur ne démarre pas.**
- **En local** : `scripts/start.sh` fait de même (tests puis serveur).

```bash
./scripts/test.sh        # lance toute la suite (unitaires + intégration)
```

Organisation :

```
tests/
├── test_models.py         # Point, Activity, Zone, DenseZone, dates, GPX
├── test_file_manager.py   # importCSV / exportResults
├── test_filter_manager.py # filtres nom / type / zone / genre
├── test_sort_manager.py   # tri par nombre / durée
├── test_search_engine.py  # zones denses + intersections (cas limites géo/temps)
└── test_integration.py    # endpoints /api/* via le test_client Flask
```

---

## 6. Régénérer le jeu de démonstration

Les itinéraires sont générés en suivant le vrai réseau routier (routage OSRM,
nécessite Internet) autour de Lyon, avec une « sortie de groupe » qui produit
des intersections entre plusieurs athlètes :

```bash
python tools/generate_demo_data.py            # réécrit data/demo/
```

---

## 7. Développement local (sans Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Recommandé : tests puis serveur (données de démo)
./scripts/start.sh                 # -> http://localhost:5000

# ou manuellement :
cd app
python app.py --csv ../data/demo/data.csv --gpx ../data/demo/GPX --demo
```

---

## 8. Arborescence

```
strava-analyzer/
├── app/                  # Code applicatif (Flask)
│   ├── app.py            # Serveur + IHM (Analyzer, routes /api/*)
│   ├── wsgi.py           # Point d'entrée gunicorn (production)
│   ├── models.py         # Point, Activity, User, Zone, DenseZone, Intersection
│   ├── file_manager.py   # Lecture CSV + GPX
│   ├── filter_manager.py # Filtres
│   ├── sort_manager.py   # Tri
│   ├── search_engine.py  # Zones denses + intersections
│   └── heatmap.py        # Heatmap (folium)
├── tests/                # Tests unitaires + intégration (joués au démarrage)
├── scripts/
│   ├── test.sh           # lance la suite de tests
│   └── start.sh          # tests puis serveur (local)
├── data/
│   ├── demo/             # Données FICTIVES (embarquées dans l'image)
│   └── real/             # Données réelles (montées en volume, hors image)
├── tools/
│   └── generate_demo_data.py
├── entrypoint.sh         # conteneur : tests puis serveur
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── requirements.txt
```
