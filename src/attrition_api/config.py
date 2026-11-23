"""Configuration lue dans les variables d'environnement et le fichier .env."""

import sys
from enum import StrEnum
from typing import Self

from pydantic import SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LONGUEUR_MIN_CLE_API = 32
VALEUR_EXEMPLE = "a-remplacer"


class Environnement(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    # Pas de valeur par défaut : on ne veut pas tourner en dev par oubli.
    app_env: Environnement
    api_key: SecretStr | None = None
    # Compte de l'API (lecture et ajout seulement).
    database_url: SecretStr | None = None
    # Compte propriétaire : création des tables, des droits et import du dataset.
    admin_database_url: SecretStr | None = None
    # Mot de passe donné au compte de l'API par create_db --roles.
    api_db_password: SecretStr | None = None

    @model_validator(mode="after")
    def verifier_prod(self) -> Self:
        if self.app_env is not Environnement.PROD:
            return self

        cle = self.api_key.get_secret_value() if self.api_key else ""
        url = self.database_url.get_secret_value() if self.database_url else ""
        erreurs = []
        if len(cle) < LONGUEUR_MIN_CLE_API or VALEUR_EXEMPLE in cle:
            erreurs.append(
                f"API_KEY doit faire au moins {LONGUEUR_MIN_CLE_API} caractères "
                "et ne pas être la valeur d'exemple"
            )
        if not url.startswith("postgresql") or VALEUR_EXEMPLE in url:
            erreurs.append(
                "DATABASE_URL doit être une URL PostgreSQL et ne pas être la valeur d'exemple"
            )
        if erreurs:
            raise ValueError(" ; ".join(erreurs))
        return self

    def url_admin(self) -> SecretStr | None:
        return self.admin_database_url or self.database_url


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as erreur:
        print(f"Configuration invalide :\n{erreur}", file=sys.stderr)
        return 1
    print(f"Configuration valide pour l'environnement : {settings.app_env.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
