import shutil

import pytest

from attrition_api.modele import (
    FICHIER_METADONNEES,
    FICHIER_MODELE,
    ArtefactInvalide,
    charger_modele,
)


@pytest.fixture(scope="module")
def modele():
    return charger_modele()


def test_artefact_sans_donnees_rh(modele):
    # L'artefact ne contient que l'estimateur, pas les jeux d'entraînement et de test.
    assert type(modele.estimateur).__name__ == "HistGradientBoostingClassifier"
    assert list(modele.estimateur.feature_names_in_) == modele.metadonnees["colonnes"]


def test_metadonnees_completes(modele):
    meta = modele.metadonnees
    assert meta["seuil"] == pytest.approx(0.4453, abs=1e-4)
    assert meta["resultats_test"]["matrice_confusion"] == {"vn": 183, "fp": 64, "fn": 14, "vp": 33}
    assert meta["versions"]["scikit-learn"] == "1.9.1"
    assert set(meta["source"]["donnees"]) == {
        "extrait_sirh.csv",
        "extrait_eval.csv",
        "extrait_sondage.csv",
    }


def test_probabilites_de_reference(modele, exemples):
    entrees = [e["entree"] for e in exemples.values()]
    attendues = [e["probabilite_attendue"] for e in exemples.values()]
    assert modele.predire(entrees) == pytest.approx(attendues, abs=1e-9)


def test_les_profils_de_reference_encadrent_le_seuil(modele, exemples):
    [a_risque, stable] = modele.predire(
        [exemples["profil_a_risque"]["entree"], exemples["profil_stable"]["entree"]]
    )
    assert a_risque >= modele.seuil > stable


def test_artefact_modifie_refuse(tmp_path):
    copie = tmp_path / FICHIER_MODELE.name
    copie.write_bytes(FICHIER_MODELE.read_bytes() + b"\x00")
    with pytest.raises(ArtefactInvalide, match="Empreinte"):
        charger_modele(copie, FICHIER_METADONNEES)


def test_artefact_intact_accepte(tmp_path):
    copie = tmp_path / FICHIER_MODELE.name
    shutil.copy(FICHIER_MODELE, copie)
    assert charger_modele(copie, FICHIER_METADONNEES).version == "1.0.0"


def test_variable_non_calculable_refusee(modele, exemples):
    # Sans le schéma de l'API, un poste inconnu donnerait une médiane manquante.
    entree = exemples["profil_stable"]["entree"] | {"poste": "Stagiaire"}
    with pytest.raises(ValueError, match="ratio_salaire_mediane_poste"):
        modele.predire([entree])
