"""Authentification par clé d'API transmise dans l'en-tête X-API-Key."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

en_tete_cle = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clé définie par la variable d'environnement API_KEY.",
)


def verifier_cle_api(
    request: Request, cle_recue: Annotated[str | None, Depends(en_tete_cle)]
) -> None:
    cle_attendue = request.app.state.settings.api_key
    if cle_attendue is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API_KEY n'est pas configurée")
    # compare_digest garde un temps de comparaison indépendant du contenu de la clé.
    if cle_recue is None or not secrets.compare_digest(
        cle_recue.encode(), cle_attendue.get_secret_value().encode()
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Clé d'API absente ou invalide",
            headers={"WWW-Authenticate": "APIKey"},
        )
