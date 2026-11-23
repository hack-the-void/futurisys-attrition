"""Crée les tables PostgreSQL et, en option, le rôle de l'API et ses droits.

Usage :
    uv run python -m attrition_api.create_db                 # crée les tables manquantes
    uv run python -m attrition_api.create_db --roles         # et le rôle de l'API
    uv run python -m attrition_api.create_db --reinitialiser # supprime puis recrée tout
    uv run python -m attrition_api.create_db --sql           # affiche le script SQL
    uv run python -m attrition_api.create_db --sql db/schema.sql

La base vient de ADMIN_DATABASE_URL, ou DATABASE_URL à défaut : il faut le compte
propriétaire. `--roles` lit API_DB_PASSWORD.
Le script SQL équivalent est versionné dans db/schema.sql.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from attrition_api.acces import ROLE_API, configurer_acces, instructions_acces
from attrition_api.config import Settings
from attrition_api.db import TABLES, Base, creer_moteur


def ddl_postgresql() -> str:
    """Script SQL de création des tables et des droits, dans le dialecte PostgreSQL."""
    dialecte = postgresql.dialect()
    instructions = []
    for table in TABLES:
        instructions.append(str(CreateTable(table).compile(dialect=dialecte)).strip())
        for index in sorted(table.indexes, key=lambda i: i.name):
            instructions.append(str(CreateIndex(index).compile(dialect=dialecte)).strip())
    instructions.append(
        "-- Droits d'accès, pour une base nommée attrition. Le rôle est créé avec son\n"
        "-- mot de passe par : uv run python -m attrition_api.create_db --roles\n"
        + ";\n".join(i.as_string(None) for i in instructions_acces("attrition", ROLE_API))
    )
    entete = "-- Généré par : uv run python -m attrition_api.create_db --sql db/schema.sql\n\n"
    return entete + ";\n\n".join(instructions) + ";\n"


def creer_tables(moteur: Engine, reinitialiser: bool = False) -> None:
    if reinitialiser:
        Base.metadata.drop_all(moteur)
    Base.metadata.create_all(moteur)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crée les tables de l'API.")
    parser.add_argument("--reinitialiser", action="store_true", help="Supprime les données")
    parser.add_argument("--roles", action="store_true", help="Configure le rôle de l'API")
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
    url = settings.url_admin()
    if url is None:
        print("ADMIN_DATABASE_URL ou DATABASE_URL doit être définie.", file=sys.stderr)
        return 1
    if args.roles and settings.api_db_password is None:
        print("--roles exige API_DB_PASSWORD.", file=sys.stderr)
        return 1

    moteur = creer_moteur(url.get_secret_value())
    creer_tables(moteur, args.reinitialiser)
    print("Tables prêtes : " + ", ".join(t.name for t in TABLES))
    if args.roles:
        configurer_acces(moteur, settings.api_db_password.get_secret_value())
        print(f"Rôle prêt : {ROLE_API} (lecture et ajout seulement)")
    moteur.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
