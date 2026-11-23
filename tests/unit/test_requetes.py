import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from attrition_api.db import creer_moteur, enregistrer_modele, enregistrer_prediction
from attrition_api.modele import charger_modele

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "interroger_db.py"
spec = importlib.util.spec_from_file_location("interroger_db", SCRIPT)
interroger_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interroger_db)

REQUETES = interroger_db.charger_requetes()


@pytest.fixture
def moteur(url_base, exemples):
    moteur = creer_moteur(url_base)
    modele = charger_modele()
    with Session(moteur) as session:
        enregistrer_modele(session, modele)
        for exemple in exemples.values():
            entree = exemple["entree"]
            [probabilite] = modele.predire([entree])
            enregistrer_prediction(session, entree, probabilite, modele, source="script")
    yield moteur
    moteur.dispose()


def test_requetes_attendues():
    assert {"dernieres", "synthese", "alertes_par_poste", "export"} <= set(REQUETES)


@pytest.mark.parametrize("nom", list(REQUETES))
def test_chaque_requete_s_execute(moteur, nom):
    with moteur.connect() as connexion:
        lignes = connexion.execute(text(REQUETES[nom])).all()
    assert lignes


def test_synthese(moteur):
    with moteur.connect() as connexion:
        [ligne] = connexion.execute(text(REQUETES["synthese"])).mappings().all()
    assert ligne["predictions"] == 3
    assert ligne["alertes"] == 2


def test_export_contient_entrees_et_sorties(moteur):
    with moteur.connect() as connexion:
        colonnes = connexion.execute(text(REQUETES["export"])).keys()
    assert {"poste", "heure_supplementaires", "probabilite", "risque_depart"} <= set(colonnes)
