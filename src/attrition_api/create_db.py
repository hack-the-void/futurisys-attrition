"""Crée les tables PostgreSQL de l'API.

Usage :
    uv run python -m attrition_api.create_db                 # crée les tables manquantes
    uv run python -m attrition_api.create_db --reinitialiser # supprime puis recrée tout
    uv run python -m attrition_api.create_db --sql           # affiche le script SQL
    uv run python -m attrition_api.create_db --sql db/schema.sql

La base vient de DATABASE_URL. Le script SQL équivalent est versionné dans db/schema.sql.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from attrition_api.config import Settings
from attrition_api.db import TABLES, Base, creer_moteur


def ddl_postgresql() -> str:
    """Script SQL de création des tables, dans le dialecte PostgreSQL."""
    dialecte = postgresql.dialect()
    instructions = []
    for table in TABLES:
        instructions.append(str(CreateTable(table).compile(dialect=dialecte)).strip())
        for index in sorted(table.indexes, key=lambda i: i.name):
            instructions.append(str(CreateIndex(index).compile(dialect=dialecte)).strip())
    entete = "-- Généré par : uv run python -m attrition_api.create_db --sql db/schema.sql\n\n"
    return entete + ";\n\n".join(instructions) + ";\n"


def creer_tables(moteur: Engine, reinitialiser: bool = False) -> None:
    if reinitialiser:
        Base.metadata.drop_all(moteur)
    Base.metadata.create_all(moteur)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crée les tables de l'API.")
    parser.add_argument("--reinitialiser", action="store_true", help="Supprime les données")
    parser.add_argument(
        "--sql",
        nargs="?",
        const="-",
        metavar="FICHIER",
        help="Écrit le SQL dans FICHIER, ou l'affiche, sans l'exécuter",
    )
    args = parser.parse_args(argv)

    if args.sql == "-":
        print(ddl_postgresql(), end="")
        return 0
    if args.sql:
        Path(args.sql).write_text(ddl_postgresql(), encoding="utf-8", newline="\n")
        return 0

    settings = Settings()
    if settings.database_url is None:
        print("DATABASE_URL n'est pas définie.", file=sys.stderr)
        return 1
    creer_tables(creer_moteur(settings.database_url.get_secret_value()), args.reinitialiser)
    print("Tables prêtes : " + ", ".join(t.name for t in TABLES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
