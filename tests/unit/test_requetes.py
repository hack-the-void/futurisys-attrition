import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from attrition_api.dataset import charger_donnees_brutes, importer_employes, predire_dataset
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
    """Base avec le mini-dataset prédit (source dataset) et trois appels (source script)."""
    moteur = creer_moteur(url_base)
    modele = charger_modele()
    with Session(moteur) as session:
        importer_employes(session, charger_donnees_brutes(DOSSIER_SOURCES), ids_test={478})
        predire_dataset(session, modele)
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
        lignes = connexion.execute(text(REQUETES["synthese"])).mappings().all()
    assert {(ligne["source"], ligne["predictions"], ligne["alertes"]) for ligne in lignes} == {
        ("dataset", 3, 2),
        ("script", 3, 2),
    }


def test_performances_test_recalculees_depuis_la_base(moteur):
    # Seul l'employé 478 est en test : il est parti et le modèle l'a signalé.
    with moteur.connect() as connexion:
        [ligne] = connexion.execute(text(REQUETES["performances_test"])).mappings().all()
    assert (ligne["employes"], ligne["departs"], ligne["vrais_positifs"]) == (1, 1, 1)
    assert ligne["rappel"] == 1


def test_export_contient_entrees_et_sorties(moteur):
    with moteur.connect() as connexion:
        colonnes = connexion.execute(text(REQUETES["export"])).keys()
    assert {"poste", "heure_supplementaires", "probabilite", "risque_depart"} <= set(colonnes)
