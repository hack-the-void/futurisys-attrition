from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from attrition_api.dataset import charger_donnees_brutes, importer_employes
from attrition_api.db import (
    EmployeDataset,
    PredictionEnregistree,
    creer_moteur,
    enregistrer_modele,
    enregistrer_prediction,
)
from attrition_api.modele import charger_modele
from attrition_api.schemas import EXEMPLE_EMPLOYE

DOSSIER_SOURCES = Path(__file__).resolve().parents[1] / "donnees" / "sources"


@pytest.fixture(scope="module")
def brut():
    return charger_donnees_brutes(DOSSIER_SOURCES)


@pytest.fixture(scope="module")
def modele():
    return charger_modele()


@pytest.fixture
def session(url_base):
    moteur = creer_moteur(url_base)
    with Session(moteur) as session:
        yield session
    moteur.dispose()


def compter(session, table, *conditions):
    return session.scalar(select(func.count()).select_from(table).where(*conditions))


def test_rapprochement_des_trois_extraits(brut):
    assert list(brut.index) == [478, 734, 1839]
    assert brut.shape[1] == 31  # toutes les colonnes, y compris celles que le modèle ignore
    assert brut["heure_supplementaires"].tolist() == [True, False, False]
    assert brut["augementation_salaire_precedente"].tolist() == [11.0, 12.0, 16.0]
    assert brut["a_quitte_l_entreprise"].tolist() == [1, 0, 0]


def test_import_des_employes(session, brut):
    assert importer_employes(session, brut, ids_test=[478]) == 3
    employe = session.get(EmployeDataset, 478)
    assert employe.jeu == "test"
    assert employe.a_quitte_l_entreprise is True
    assert employe.departement == "Commercial"
    assert session.get(EmployeDataset, 734).jeu == "train"


def test_import_sans_prediction(session, brut):
    importer_employes(session, brut, ids_test=[478])
    assert compter(session, PredictionEnregistree) == 0


def test_reimport_sans_doublon_et_sans_perdre_les_predictions(session, brut, modele):
    importer_employes(session, brut, ids_test=[478])
    enregistrer_modele(session, modele)
    enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.9, modele, source="api", employe_id=478)

    importer_employes(session, brut, ids_test=[478, 734])

    assert compter(session, EmployeDataset) == 3
    assert session.get(EmployeDataset, 734).jeu == "test"
    [prediction] = session.scalars(select(PredictionEnregistree)).all()
    assert prediction.entree.employe_id == 478
