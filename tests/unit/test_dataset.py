from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from attrition_api.dataset import (
    charger_donnees_brutes,
    importer_employes,
    predire_dataset,
)
from attrition_api.db import (
    EmployeDataset,
    Entree,
    PredictionEnregistree,
    creer_moteur,
    enregistrer_modele,
    enregistrer_prediction,
)
from attrition_api.modele import charger_modele
from attrition_api.schemas import EXEMPLE_EMPLOYE

DOSSIER_SOURCES = Path(__file__).resolve().parents[1] / "donnees" / "sources"
# Les mini-CSV contiennent les employés 478, 734 et 1839, dans cet ordre.
PROFILS = ["depart", "stable", "premier_emploi"]


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


def test_predictions_du_dataset_identiques_a_l_api(session, brut, modele, exemples):
    importer_employes(session, brut, ids_test=[478])
    assert predire_dataset(session, modele) == 3

    predictions = session.scalars(
        select(PredictionEnregistree).join(Entree).order_by(Entree.employe_id)
    ).all()
    assert [p.entree.employe_id for p in predictions] == [478, 734, 1839]
    assert {p.entree.source for p in predictions} == {"dataset"}
    # Même modèle, mêmes champs : mêmes probabilités que par l'API.
    assert [p.probabilite for p in predictions] == pytest.approx(
        [exemples[nom]["probabilite_attendue"] for nom in PROFILS], abs=1e-9
    )


def test_reimport_sans_doublon_et_sans_toucher_aux_appels_api(session, brut, modele):
    enregistrer_modele(session, modele)
    enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.5, modele, source="api")
    for _ in range(2):
        importer_employes(session, brut, ids_test=[478])
        predire_dataset(session, modele)

    assert compter(session, EmployeDataset) == 3
    assert compter(session, Entree, Entree.source == "dataset") == 3
    assert compter(session, Entree, Entree.source == "api") == 1
    assert compter(session, PredictionEnregistree) == 4
