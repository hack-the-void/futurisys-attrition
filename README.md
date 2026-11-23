# Futurisys – Prédiction de l'attrition

[![CI](https://github.com/hack-the-void/futurisys-attrition/actions/workflows/ci.yml/badge.svg)](https://github.com/hack-the-void/futurisys-attrition/actions/workflows/ci.yml)

Ce dépôt reprend le modèle du projet 4 du parcours Data Scientist d'OpenClassrooms.
Une API FastAPI le sert pour estimer le risque de démission d'un employé, et chaque
prédiction est enregistrée dans PostgreSQL, avec le dataset complet du projet 4. Le projet est un POC déployé en local avec
Docker Compose, comme la mission l'autorise.

## Le modèle

L'entraînement utilise trois sources RH de TechNova Partners (SIRH, évaluations, sondage),
soit 1 470 employés au total. Le `HistGradientBoostingClassifier` reçoit 44 variables
construites à partir de 25 champs bruts.

Au seuil de 0,445, choisi pour maximiser le F2 sur les données d'entraînement, le modèle
détecte 33 des 47 départs du jeu de test (70 % de rappel). Sur les 97 alertes, 33
correspondent à un départ (34 % de précision). La PR-AUC vaut 0,50 pour un taux de départ
de 16 % sur les 294 employés du test. Une alerte sert à orienter un entretien.

Les données RH et l'artefact d'origine, qui contient les jeux d'entraînement et de test,
restent hors de Git. [scripts/exporter_modele.py](scripts/exporter_modele.py) en extrait le
modèle seul dans [src/attrition_api/artefacts/](src/attrition_api/artefacts/). Il vérifie
d'abord que l'API reconstruit à l'identique les 44 variables des 1 470 employés. Le fichier
`modele_attrition.json` décrit le seuil, les médianes de salaire figées, les résultats du
test, les versions des bibliothèques et l'empreinte des données. Les conditions de
réutilisation du modèle sont dans [docs/STANDARDS.md](docs/STANDARDS.md#artefact-de-modèle).

## Installer et tester

```bash
git clone https://github.com/hack-the-void/futurisys-attrition.git
cd futurisys-attrition
uv sync --locked
uv run --locked pytest
```

Le projet utilise Python 3.12, la version avec laquelle le modèle a été sérialisé.
[uv](https://docs.astral.sh/uv/getting-started/installation/) installe Python si nécessaire.
Sans autre réglage, les tests utilisent une base SQLite temporaire. Pour les lancer sur
PostgreSQL, comme en CI, définir `TEST_DATABASE_URL` vers une base dédiée : les tests en
vident les tables.

pytest affiche la couverture dans le terminal et échoue sous 80 %. Pour un rapport HTML,
lancer `uv run --locked pytest --cov-report=html`, puis ouvrir `htmlcov/index.html`.

<details>
<summary>Installation avec pip</summary>

Dans un environnement virtuel Python 3.12 activé, lancer les commandes suivantes.

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
python -m pytest
```

</details>

## Configuration locale

Copier `.env.example` vers `.env` et remplacer les valeurs `a-remplacer`. Lancer ensuite
`uv run --locked python -m attrition_api.config` pour vérifier le fichier. Les variables
définies dans le terminal priment sur celles du fichier. `.env` est ignoré par Git.

| Variable | Valeur attendue |
| --- | --- |
| `APP_ENV` | Obligatoire. Utiliser `dev` en local, `test` en CI et `prod` pour la livraison. |
| `API_KEY` | Clé attendue dans l'en-tête `X-API-Key`. En `prod`, au moins 32 caractères. |
| `POSTGRES_PASSWORD` | Mot de passe du compte propriétaire, créé par `docker-compose.yml`. |
| `API_DB_PASSWORD` | Mot de passe du rôle `api_attrition`, limité à la lecture et à l'ajout. |
| `DATABASE_URL` | URL PostgreSQL de l'API, avec le rôle `api_attrition`. Obligatoire pour démarrer l'API. |
| `ADMIN_DATABASE_URL` | URL du compte propriétaire, pour créer les tables et importer le dataset. |

Le contrôle de production refuse les valeurs d'exemple. La commande affiche l'environnement
ou l'erreur de validation en masquant les valeurs saisies. Pour générer une clé, lancer
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Déployer en local

Avec [Docker](https://docs.docker.com/get-docker/), une seule commande lance PostgreSQL 17
et l'API. Le service `init-db` crée les tables et le rôle de l'API avant qu'elle démarre.

```bash
docker compose up -d --build
```

Pour développer, on peut aussi lancer la base seule et l'API avec uv.

```bash
docker compose up -d db
uv run --locked python -m attrition_api.create_db --roles
uv run --locked uvicorn attrition_api.main:app --reload
```

Dans les deux cas, l'API écoute sur http://127.0.0.1:8000. Les ports ne sont ouverts que
sur cette machine. Utiliser `127.0.0.1` plutôt que `localhost` dans `DATABASE_URL` : sous
Windows, `localhost` passe d'abord par IPv6, et la connexion à Docker reste bloquée.
`docker compose down` arrête les conteneurs et garde les données. Ajouter `-v` pour les
effacer.

## Utiliser l'API

La documentation interactive est sur `/docs` (Swagger) et `/redoc`. Le schéma OpenAPI est
sur `/openapi.json`. Au démarrage, l'API vérifie la configuration, l'empreinte du modèle et
la présence des tables. Elle refuse de démarrer si l'une de ces vérifications échoue.

| Route | Authentification | Rôle |
| --- | --- | --- |
| `GET /health` | Non | État du service et version du modèle |
| `GET /modele` | Oui | Seuil, variables et résultats du modèle sur le test |
| `GET /employes` | Oui | Employés de la base, pour en choisir un (`?departement=`, `?poste=`, `?limite=`, `?decalage=`) |
| `GET /employes/{id}` | Oui | Les 25 champs RH d'un employé, sans son départ réel |
| `POST /employes/{id}/predictions` | Oui | Fait passer l'employé choisi par le modèle, enregistre et renvoie la prédiction |
| `POST /predictions` | Oui | Même calcul pour un employé saisi à la main (25 champs en JSON) |
| `GET /predictions` | Oui | Dernières prédictions (`?limite=20`, 100 au plus) |
| `GET /predictions/{id}` | Oui | Une prédiction et les données qui l'ont produite |

L'utilisateur choisit un employé, puis demande sa prédiction. Le modèle la calcule à ce
moment-là : rien n'est calculé à l'avance.

```bash
curl -X POST http://127.0.0.1:8000/employes/478/predictions -H "X-API-Key: $API_KEY"
```

```json
{"id_prediction": 1, "id_employe": 478, "probabilite_depart": 0.963, "risque_depart": true,
 "seuil": 0.445, "version_modele": "1.0.0", "calculee_le": "2026-11-23T18:28:01Z"}
```

`POST /predictions` reçoit à la place les 25 champs RH en JSON, pour un employé absent de
la base. L'exemple complet est prérempli dans Swagger.

Un employé inconnu renvoie 404. Une entrée invalide renvoie une erreur 422 qui détaille les champs en cause : champ
manquant ou inconnu, valeur hors domaine, modalité absente de l'entraînement, ou durées
incohérentes (par exemple plus d'ancienneté que d'expérience). Elle n'est pas enregistrée.

## Base de données

Quatre tables : `employes` (le dataset complet), `modeles`, `entrees` (les 25 champs envoyés
au modèle) et `predictions`. Le schéma, les droits d'accès, l'import et les requêtes sont
décrits dans
[docs/BASE_DE_DONNEES.md](docs/BASE_DE_DONNEES.md). Le script SQL est dans
[db/schema.sql](db/schema.sql).

```bash
uv run python scripts/importer_dataset.py --source ../technova-attrition  # 1 470 employés
uv run python scripts/interroger_db.py performances_test  # sur les employés déjà prédits
```

## Authentification et sécurité

- **Clé d'API :** les routes du modèle exigent l'en-tête `X-API-Key`, comparé à `API_KEY`
  en temps constant. Une clé absente ou fausse renvoie 401. Si aucune clé n'est configurée,
  l'API renvoie 503 au lieu de laisser passer les appels. Dans Swagger, la clé se saisit
  avec le bouton **Authorize**.
- **Secrets :** ils sont lus depuis l'environnement ou depuis `.env`, qui n'est pas
  versionné ni copié dans l'image Docker (`.dockerignore`). En production, ils viennent des
  secrets GitHub et sont contrôlés avant la livraison. Gitleaks les recherche à chaque push.
- **Modèle :** joblib exécute du code au chargement. L'API ne charge le fichier que si son
  empreinte SHA-256 correspond à celle des métadonnées. Cela protège contre un fichier
  corrompu ou remplacé seul, mais pas contre une modification du dépôt lui-même.
- **Base :** l'API se connecte avec un rôle qui ne peut que lire et ajouter des
  prédictions, sans modification ni suppression. Dans le dataset, il ne lit que les champs
  du modèle, pas le départ réel. Les requêtes passent
  par SQLAlchemy, avec des paramètres liés, ce qui écarte les injections SQL. Le conteneur
  de l'API tourne sans privilèges root.
- **Données :** l'artefact versionné ne contient aucune donnée RH, et le dataset reste hors
  de Git. Seuls trois employés du jeu de test (478, 734 et 1839) sont versionnés : ils
  servent d'exemple dans Swagger et de références dans les tests.

## Travailler sur le dépôt

| Dossier | Contenu |
| --- | --- |
| [src/attrition_api/](src/attrition_api/) | `config.py` (configuration), `features.py` (calcul des variables), `modele.py` (chargement et prédiction), `schemas.py` (validation), `securite.py` (clé d'API), `db.py` (tables), `create_db.py` (création de la base), `acces.py` (rôle de l'API), `dataset.py` (import du dataset), `main.py` (routes) |
| [tests/](tests/) | Tests unitaires dans `unit/`, tests de l'API dans `fonctionnels/` |
| [scripts/](scripts/) | Export du modèle, import du dataset, requêtes sur la base |
| [db/](db/) | Script SQL, requêtes nommées et exemples |
| [docs/](docs/) | Conventions, pipeline CI/CD et base de données |

Avant d'ouvrir une pull request vers `main`, lancer `uv run --locked ruff check .`,
`uv run --locked ruff format --check .` et `uv run --locked pytest`. Les conventions de
branche et de commit sont dans [docs/STANDARDS.md](docs/STANDARDS.md).

Après un changement de dépendances, exporter de nouveau les fichiers pour pip depuis `uv.lock`.
Après un changement de `db.py`, régénérer `db/schema.sql`.

```bash
uv export --locked --no-dev --no-hashes --no-emit-project -o requirements.txt
uv export --locked --no-hashes --no-emit-project -o requirements-dev.txt
uv run --locked python -m attrition_api.create_db --sql db/schema.sql
```

GitHub Actions lance Ruff, pytest sur PostgreSQL, la construction de l'image Docker et
Gitleaks à chaque push et sur les pull requests vers `main`. Un tag de version déclenche la
construction du paquet et la publication d'une GitHub Release. La procédure est dans
[docs/CI_CD.md](docs/CI_CD.md).

Projet réalisé par Benjamin Thery dans le cadre du parcours Data Scientist d'OpenClassrooms.
