"""Rôle PostgreSQL de l'API et droits d'accès aux tables.

Deux comptes, chacun avec le minimum de droits nécessaire :

| Compte | Utilisé par | Droits |
| --- | --- | --- |
| propriétaire (`POSTGRES_USER`) | `create_db`, import du dataset, analyses | Tout |
| `api_attrition` | l'API | Lire et ajouter dans `modeles`, `entrees`, `predictions` |

L'API ne peut ni modifier ni supprimer une prédiction, ni lire le dataset `employes`, ni
changer le schéma. Une faille dans l'API ne peut donc pas effacer l'historique.
"""

from psycopg import sql
from sqlalchemy import Engine, text

ROLE_API = "api_attrition"
TABLES_API = ["modeles", "entrees", "predictions"]
SEQUENCES_API = ["entrees_id_seq", "predictions_id_seq"]


def instructions_acces(base: str, role_api: str = ROLE_API) -> list[sql.Composed]:
    """Les droits à appliquer, une fois le rôle créé."""
    role = sql.Identifier(role_api)
    return [
        # Seuls le propriétaire et le rôle de l'API peuvent se connecter à la base.
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(base)),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(base), role),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role),
        # On repart de zéro pour que des droits accordés à la main ne restent pas.
        sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role),
        sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(role),
        sql.SQL("GRANT SELECT, INSERT ON {} TO {}").format(
            sql.SQL(", ").join(map(sql.Identifier, TABLES_API)), role
        ),
        sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
            sql.SQL(", ").join(map(sql.Identifier, SEQUENCES_API)), role
        ),
    ]


def configurer_acces(moteur: Engine, mot_de_passe: str, role_api: str = ROLE_API) -> None:
    """Crée ou met à jour le rôle de l'API, puis applique ses droits sur les tables.

    À relancer après `create_db --reinitialiser` : supprimer une table supprime ses droits.
    """
    if moteur.dialect.name != "postgresql":
        raise ValueError("Les rôles et les droits ne sont gérés que sous PostgreSQL")

    with moteur.begin() as connexion:
        brute = connexion.connection.driver_connection
        base = connexion.scalar(text("SELECT current_database()"))
        existe = connexion.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role_api}
        )
        # Le mot de passe passe par sql.Literal : PostgreSQL n'accepte pas de paramètre ici.
        requete = sql.SQL("{} ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.SQL("ALTER" if existe else "CREATE"),
            sql.Identifier(role_api),
            sql.Literal(mot_de_passe),
        )
        connexion.exec_driver_sql(requete.as_string(brute))
        for instruction in instructions_acces(base, role_api):
            connexion.exec_driver_sql(instruction.as_string(brute))
