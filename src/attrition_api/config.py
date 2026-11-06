"""Configuration chargée depuis l'environnement et le fichier .env local."""

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,  # Masque les valeurs reçues dans les erreurs.
    )

    # APP_ENV est obligatoire pour éviter de basculer en dev si la variable manque.
    app_env: Environnement
    api_key: SecretStr | None = None
    database_url: SecretStr | None = None

    @model_validator(mode="after")
    def _exiger_les_secrets_en_prod(self) -> Self:
        if self.app_env is not Environnement.PROD:
            return self

        cle = self.api_key.get_secret_value() if self.api_key else ""
        url = self.database_url.get_secret_value() if self.database_url else ""

        problemes = []
        if len(cle) < LONGUEUR_MIN_CLE_API or VALEUR_EXEMPLE in cle:
            problemes.append(
                f"API_KEY doit faire au moins {LONGUEUR_MIN_CLE_API} caractères "
                "et ne pas être la valeur d'exemple"
            )
        if not url.startswith("postgresql") or VALEUR_EXEMPLE in url:
            problemes.append(
                "DATABASE_URL doit être une URL PostgreSQL et ne pas être la valeur d'exemple"
            )
        if problemes:
            raise ValueError(" ; ".join(problemes))
        return self


def main() -> int:
    """Valide la configuration et affiche l'environnement actif."""
    try:
        settings = Settings()
    except ValidationError as erreur:
        print(f"Configuration invalide :\n{erreur}", file=sys.stderr)
        return 1

    print(f"Configuration valide pour l'environnement : {settings.app_env.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
