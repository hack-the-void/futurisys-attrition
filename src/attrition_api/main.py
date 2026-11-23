"""API FastAPI qui expose le modèle de prédiction de l'attrition.

Lancement local : `uv run uvicorn attrition_api.main:app --reload`
Documentation interactive : http://127.0.0.1:8000/docs
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from attrition_api import __version__
from attrition_api.config import Settings
from attrition_api.db import (
    CHAMPS_ENTREE,
    PredictionEnregistree,
    creer_moteur,
    enregistrer_modele,
    enregistrer_prediction,
    lister_predictions,
    tables_manquantes,
)
from attrition_api.modele import ModeleAttrition, charger_modele
from attrition_api.schemas import (
    Employe,
    EtatService,
    InfosModele,
    Prediction,
    PredictionDetaillee,
)
from attrition_api.securite import verifier_cle_api

DESCRIPTION = """
Estime le risque de démission d'un employé à partir de 25 champs RH.

Une alerte (`risque_depart`) signale un profil à rencontrer en entretien. Elle ne suffit
pas à elle seule pour prendre une décision RH. Au seuil retenu, le modèle détecte 70 % des
départs du jeu de test, et une alerte sur trois correspond à un départ.

Chaque prédiction est enregistrée dans PostgreSQL avec les données reçues.
Les routes du modèle exigent l'en-tête `X-API-Key`.
"""


@asynccontextmanager
async def cycle_de_vie(app: FastAPI) -> AsyncIterator[None]:
    # Configuration, modèle et base sont vérifiés au démarrage : un défaut arrête le service.
    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL est obligatoire pour lancer l'API")
    modele = charger_modele()
    moteur = creer_moteur(settings.database_url.get_secret_value())
    if manquantes := tables_manquantes(moteur):
        raise RuntimeError(
            f"Tables absentes ({', '.join(manquantes)}) : "
            "lancer `python -m attrition_api.create_db`"
        )
    with Session(moteur) as session:
        enregistrer_modele(session, modele)

    app.state.settings, app.state.modele, app.state.moteur = settings, modele, moteur
    yield
    moteur.dispose()


app = FastAPI(
    title="Futurisys – Prédiction de l'attrition",
    description=DESCRIPTION,
    version=__version__,
    lifespan=cycle_de_vie,
)


def modele_charge(request: Request) -> ModeleAttrition:
    return request.app.state.modele


def session_base(request: Request) -> Iterator[Session]:
    with Session(request.app.state.moteur) as session:
        yield session


ModeleCharge = Annotated[ModeleAttrition, Depends(modele_charge)]
SessionBase = Annotated[Session, Depends(session_base)]
protegee = [Depends(verifier_cle_api)]


@app.get("/health", tags=["Service"])
def etat(modele: ModeleCharge) -> EtatService:
    """Indique que le service répond et quel modèle il utilise. Sans authentification."""
    return EtatService(statut="ok", version_api=__version__, version_modele=modele.version)


@app.get("/modele", tags=["Modèle"], dependencies=protegee)
def infos_modele(modele: ModeleCharge) -> InfosModele:
    """Décrit le modèle chargé : seuil, variables et résultats sur le jeu de test."""
    meta = modele.metadonnees
    return InfosModele(
        version=meta["version"],
        algorithme=meta["algorithme"],
        seuil=meta["seuil"],
        date_export=meta["date_export"],
        variables=meta["colonnes"],
        resultats_test=meta["resultats_test"],
    )


@app.post(
    "/predictions",
    tags=["Prédictions"],
    dependencies=protegee,
    status_code=status.HTTP_201_CREATED,
)
def predire(employe: Employe, modele: ModeleCharge, session: SessionBase) -> Prediction:
    """Calcule la probabilité de départ d'un employé et l'enregistre avec les données reçues."""
    donnees = employe.model_dump()
    [probabilite] = modele.predire([donnees])
    ligne = enregistrer_prediction(session, donnees, probabilite, modele, source="api")
    return Prediction.depuis_base(ligne)


@app.get("/predictions", tags=["Prédictions"], dependencies=protegee)
def dernieres_predictions(
    session: SessionBase, limite: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[Prediction]:
    """Liste les dernières prédictions enregistrées, de la plus récente à la plus ancienne."""
    return [Prediction.depuis_base(ligne) for ligne in lister_predictions(session, limite)]


@app.get("/predictions/{id_prediction}", tags=["Prédictions"], dependencies=protegee)
def lire_prediction(id_prediction: int, session: SessionBase) -> PredictionDetaillee:
    """Renvoie une prédiction enregistrée et les données RH qui l'ont produite."""
    ligne = session.get(PredictionEnregistree, id_prediction)
    if ligne is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prédiction introuvable")
    entree = Employe(**{champ: getattr(ligne.entree, champ) for champ in CHAMPS_ENTREE})
    return PredictionDetaillee(**Prediction.depuis_base(ligne).model_dump(), entree=entree)
