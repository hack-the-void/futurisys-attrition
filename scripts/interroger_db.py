"""Exécute une requête de db/requetes.sql sur la base définie par DATABASE_URL.

Usage :
    uv run python scripts/interroger_db.py --liste
    uv run python scripts/interroger_db.py alertes_par_poste
    uv run python scripts/interroger_db.py export --csv db/exemples/predictions_fictives.csv
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from attrition_api.config import Settings
from attrition_api.db import creer_moteur

FICHIER_REQUETES = Path(__file__).resolve().parents[1] / "db" / "requetes.sql"


def charger_requetes(fichier: Path = FICHIER_REQUETES) -> dict[str, str]:
    """Découpe le fichier SQL en requêtes nommées par leur ligne « -- nom: »."""
    blocs = re.split(r"^-- nom: *(\w+) *$", fichier.read_text(encoding="utf-8"), flags=re.M)
    return {nom: sql.strip().rstrip(";") for nom, sql in zip(blocs[1::2], blocs[2::2], strict=True)}


def main() -> int:
    requetes = charger_requetes()
    parser = argparse.ArgumentParser(description="Interroge les prédictions enregistrées.")
    parser.add_argument("requete", nargs="?", choices=list(requetes))
    parser.add_argument("--liste", action="store_true", help="Liste les requêtes disponibles")
    parser.add_argument("--csv", type=Path, help="Écrit le résultat dans un fichier CSV")
    args = parser.parse_args()

    if args.liste or args.requete is None:
        print("\n".join(requetes))
        return 0

    settings = Settings()
    if settings.database_url is None:
        print("DATABASE_URL n'est pas définie.", file=sys.stderr)
        return 1
    moteur = creer_moteur(settings.database_url.get_secret_value())
    with moteur.connect() as connexion:
        resultat = pd.read_sql(text(requetes[args.requete]), connexion)
    moteur.dispose()

    if args.csv:
        resultat.to_csv(args.csv, index=False, lineterminator="\n")
        print(f"{len(resultat)} lignes écrites dans {args.csv}")
    else:
        with pd.option_context("display.width", 200, "display.max_columns", 20):
            print(resultat.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
