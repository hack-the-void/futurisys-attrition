import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from attrition_api.dataset import charger_donnees_brutes, importer_employes
from attrition_api.db import creer_moteur, enregistrer_modele, enregistrer_prediction
from attrition_api.modele import charger_modele

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "interroger_db.py"
DOSSIER_SOURCES = Path(__file__).resolve().parents[1] / "donnees" / "sources"
spec = importlib.util.spec_from_file_location("interroger_db", SCRIPT)
interroger_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interroger_db)

REQUETES = interroger_db.charger_requetes()


@pytest.fixture
def moteur(url_base, exemples):
    """Le mini-dataset, ses trois employés choisis dans l'API, et le 478 une seconde fois."""
    moteur = creer_moteur(url_base)
    modele = charger_modele()
    with Session(moteur) as session:
        importer_employes(session, charger_donnees_brutes(DOSSIER_SOURCES), ids_test={478, 1839})
        enregistrer_modele(session, modele)
        choix = [*exemples.values(), exemples["depart"]]
        for exemple in choix:
            entree = exemple["entree"]
            [probabilite] = modele.predire([entree])
            enregistrer_prediction(
                session,
                entree,
                probabilite,
                modele,
                source="api",
                employe_id=exemple["id_employee"],
            )
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
        lignes = connexion.execute(text(REQUETES["synthese"])).mappings().all()
    assert [(ligne["source"], ligne["predictions"], ligne["alertes"]) for ligne in lignes] == [
        ("api", 4, 3)
    ]


def test_performances_test_recalculees_depuis_la_base(moteur):
    # En test : le 478, parti et signalé (prédit deux fois, compté une fois), et le 1839,
    # resté mais signalé.
    with moteur.connect() as connexion:
        [ligne] = connexion.execute(text(REQUETES["performances_test"])).mappings().all()
    assert (ligne["employes"], ligne["departs"], ligne["vrais_positifs"]) == (2, 1, 1)
    assert (ligne["fausses_alertes"], ligne["departs_manques"]) == (1, 0)
    assert ligne["rappel"] == 1


def test_export_contient_entrees_et_sorties(moteur):
    with moteur.connect() as connexion:
        colonnes = connexion.execute(text(REQUETES["export"])).keys()
    assert {"poste", "heure_supplementaires", "probabilite", "risque_depart"} <= set(colonnes)
