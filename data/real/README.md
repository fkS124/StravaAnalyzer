# Données réelles (non versionnées)

Ce dossier est **volontairement vide** dans le dépôt Git.

Les données Strava réelles ne sont **pas publiées** pour des raisons de
confidentialité / RGPD (cf. `.gitignore`). Le dépôt n'embarque que le jeu de
**démonstration fictif** (`data/demo/`).

## Pour exécuter l'application sur des données réelles

Placez ici, en local :

```
data/real/
├── data.csv          # métadonnées des activités (voir format dans le README racine)
└── GPX/
    ├── <activity_id>.gpx
    └── ...
```

Puis lancez le profil dédié :

```bash
docker compose --profile real up --build   # -> http://localhost:5001
```
