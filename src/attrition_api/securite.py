"""Vérification de la clé d'API envoyée dans l'en-tête X-API-Key."""

import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

en_tete_cle = APIKeyHeader(name="X-API-Key", auto_error=False)


def verifier_cle_api(request: Request, cle_recue: str | None = Depends(en_tete_cle)):
    cle_attendue = request.app.state.settings.api_key
    if cle_attendue is None:
        raise HTTPException(503, "API_KEY n'est pas configurée")
    # compare_digest compare en temps constant.
    if cle_recue is None or not secrets.compare_digest(
        cle_recue.encode(), cle_attendue.get_secret_value().encode()
    ):
        raise HTTPException(
            401, "Clé d'API absente ou invalide", headers={"WWW-Authenticate": "APIKey"}
        )
