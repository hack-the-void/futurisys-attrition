"""Insère le dataset complet du projet 4 dans PostgreSQL.

Les CSV et l'artefact d'origine restent hors du dépôt : le script les lit dans le dossier
du projet 4. Le découpage train/test vient de l'artefact d'origine, pour pouvoir comparer
en SQL les prédictions demandées à l'API aux départs réels du jeu de test.

Aucune prédiction n'est calculée : l'utilisateur choisit un employé, et l'API le fait passer
par le modèle à ce moment-là (POST /employes/{id}/predictions).

Le script utilise ADMIN_DATABASE_URL, ou DATABASE_URL à défaut : il écrit dans la table
`employes`, ce que le rôle de l'API n'a pas le droit de faire.

Usage :
    uv run python scripts/importer_dataset.py --source ../technova-attrition
"""

import argparse
import sys
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from attrition_api.config import Settings
from attrition_api.dataset import charger_donnees_brutes, importer_employes
from attrition_api.db import creer_moteur


def main() -> int:
    parser = argparse.ArgumentParser(description="Insère le dataset du projet 4 en base.")
    parser.add_argument("--source", type=Path, required=True, help="Dossier du projet 4")
    args = parser.parse_args()

    settings = Settings()
    url = settings.url_admin()
    if url is None:
        print("ADMIN_DATABASE_URL ou DATABASE_URL doit être définie.", file=sys.stderr)
        return 1

    brut = charger_donnees_brutes(args.source / "data")
    ids_test = joblib.load(args.source / "artefacts" / "modele_final.joblib")["X_test"].index

    moteur = creer_moteur(url.get_secret_value())
    with Session(moteur) as session:
        nombre = importer_employes(session, brut, ids_test)
        print(f"{nombre} employés dans la table employes ({len(ids_test)} en test).")
    moteur.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
