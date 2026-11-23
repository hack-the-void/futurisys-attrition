"""Insère le dataset complet du projet 4 dans PostgreSQL, puis le fait prédire par le modèle.

Les CSV et l'artefact d'origine restent hors du dépôt : le script les lit dans le dossier
du projet 4. Le découpage train/test vient de l'artefact d'origine, pour que la base
permette de recalculer les résultats du test en SQL.

Le script utilise ADMIN_DATABASE_URL, ou DATABASE_URL à défaut : il remplace le contenu de
la table `employes`, ce que le rôle de l'API n'a pas le droit de faire.

Usage :
    uv run python scripts/importer_dataset.py --source ../../technova-attrition
    uv run python scripts/importer_dataset.py --source ... --sans-predictions
"""

import argparse
import sys
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from attrition_api.config import Settings
from attrition_api.dataset import charger_donnees_brutes, importer_employes, predire_dataset
from attrition_api.db import creer_moteur
from attrition_api.modele import charger_modele


def main() -> int:
    parser = argparse.ArgumentParser(description="Insère le dataset du projet 4 en base.")
    parser.add_argument("--source", type=Path, required=True, help="Dossier du projet 4")
    parser.add_argument("--sans-predictions", action="store_true")
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
        print(f"{nombre} employés insérés dans la table employes ({len(ids_test)} en test).")
        if not args.sans_predictions:
            nombre = predire_dataset(session, charger_modele())
            print(f"{nombre} entrées et prédictions enregistrées (source « dataset »).")
    moteur.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
