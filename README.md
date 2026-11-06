# Futurisys – Prédiction de l'attrition

[![CI](https://github.com/hack-the-void/futurisys-attrition/actions/workflows/ci.yml/badge.svg)](https://github.com/hack-the-void/futurisys-attrition/actions/workflows/ci.yml)

Ce dépôt reprend le modèle du projet 4 du parcours Data Scientist d'OpenClassrooms.
Le but est de le servir via une API qui estime le risque de démission d'un employé.
Pour l'instant, le dépôt contient la configuration, ses tests et le pipeline GitHub Actions.
Il reste à brancher le modèle, à créer l'API FastAPI et à enregistrer les prédictions dans PostgreSQL.

## Le modèle

L'entraînement utilise trois sources RH de TechNova Partners (SIRH, évaluations, sondage),
soit 1 470 employés au total. Le `HistGradientBoostingClassifier` reçoit 44 variables
construites à partir de 25 champs bruts.

Au seuil de 0,445, choisi pour maximiser le F2 sur les données d'entraînement, le modèle
détecte 33 des 47 départs du jeu de test (70 % de rappel). Sur les 97 alertes, 33
correspondent à un départ (34 % de précision). La PR-AUC vaut 0,50 pour un taux de départ
de 16 % sur les 294 employés du test. Une alerte sert à orienter un entretien.

Les données RH et le fichier du modèle restent hors de Git. Les conditions de réutilisation
du modèle sont dans [docs/STANDARDS.md](docs/STANDARDS.md#artefact-de-modèle).

## Installer et tester

```bash
git clone https://github.com/hack-the-void/futurisys-attrition.git
cd futurisys-attrition
uv sync --locked
uv run --locked pytest
```

Le projet utilise Python 3.12, la version avec laquelle le modèle a été sérialisé.
[uv](https://docs.astral.sh/uv/getting-started/installation/) installe Python si nécessaire.

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

Copier `.env.example` vers `.env`, puis lancer `uv run --locked python -m attrition_api.config`.
Les variables définies dans le terminal priment sur celles du fichier. `.env` est ignoré par Git.

| Variable | Valeur attendue |
| --- | --- |
| `APP_ENV` | Obligatoire. Utiliser `dev` en local, `test` en CI et `prod` pour la livraison. |
| `API_KEY` | En `prod`, clé d'au moins 32 caractères. |
| `DATABASE_URL` | En `prod`, URL PostgreSQL. |

Le contrôle de production refuse les valeurs d'exemple. La commande affiche l'environnement
ou l'erreur de validation en masquant les valeurs saisies.

## Travailler sur le dépôt

La configuration est dans [src/attrition_api/config.py](src/attrition_api/config.py) et ses
tests dans [tests/unit/](tests/unit/). Avant d'ouvrir une pull request vers `main`, lancer
`uv run --locked ruff check .`, `uv run --locked ruff format --check .` et
`uv run --locked pytest`. Les conventions de branche et de commit sont dans
[docs/STANDARDS.md](docs/STANDARDS.md).

Après un changement de dépendances, exporter de nouveau les fichiers pour pip depuis `uv.lock`.

```bash
uv export --locked --no-dev --no-hashes --no-emit-project -o requirements.txt
uv export --locked --no-hashes --no-emit-project -o requirements-dev.txt
```

GitHub Actions lance Ruff, pytest et Gitleaks à chaque push et sur les pull requests vers
`main`. Un tag de version déclenche la construction du paquet et la publication d'une
GitHub Release. La procédure est dans [docs/CI_CD.md](docs/CI_CD.md).

Projet réalisé par Benjamin Thery dans le cadre du parcours Data Scientist d'OpenClassrooms.
