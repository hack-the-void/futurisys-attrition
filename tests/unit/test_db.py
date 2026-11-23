from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from attrition_api.create_db import ddl_postgresql, main
from attrition_api.db import (
    CHAMPS_ENTREE,
    PredictionEnregistree,
    creer_moteur,
    enregistrer_modele,
    enregistrer_prediction,
    lister_predictions,
)
from attrition_api.modele import ModeleAttrition, charger_modele
from attrition_api.schemas import EXEMPLE_EMPLOYE, Employe

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


@pytest.fixture(scope="module")
def modele():
    return charger_modele()


@pytest.fixture
def session(url_base, modele):
    moteur = creer_moteur(url_base)
    with Session(moteur) as session:
        enregistrer_modele(session, modele)
        yield session
    moteur.dispose()


def test_colonnes_de_la_table_entrees_identiques_au_schema_api():
    assert CHAMPS_ENTREE == list(Employe.model_fields)


def test_schema_sql_a_jour():
    # Après un changement de db.py : uv run python -m attrition_api.create_db --sql db/schema.sql
    assert SCHEMA_SQL.read_text(encoding="utf-8") == ddl_postgresql()


def test_enregistrer_et_relire(session, modele):
    ligne = enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.9, modele, source="script")
    assert ligne.id is not None
    assert ligne.risque_depart is True
    assert ligne.entree.recue_le is not None
    assert lister_predictions(session, 10) == [ligne]


def test_risque_calcule_avec_le_seuil(session, modele):
    sous_le_seuil = enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.1, modele, source="script")
    assert sous_le_seuil.risque_depart is False


def test_une_seule_prediction_par_entree_et_par_version(session, modele):
    ligne = enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.5, modele, source="script")
    session.add(
        PredictionEnregistree(
            entree_id=ligne.entree_id,
            version_modele=modele.version,
            probabilite=0.4,
            seuil=modele.seuil,
            risque_depart=False,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_probabilite_hors_bornes_refusee_par_la_base(session, modele):
    with pytest.raises(IntegrityError):
        enregistrer_prediction(session, EXEMPLE_EMPLOYE, 1.5, modele, source="script")


def test_enregistrer_modele_deux_fois_sans_doublon(session, modele):
    enregistrer_modele(session, modele)


def test_meme_version_avec_un_autre_fichier_refusee(session, modele):
    autre = ModeleAttrition(modele.estimateur, modele.metadonnees | {"sha256_modele": "0" * 64})
    with pytest.raises(RuntimeError, match="déjà enregistrée"):
        enregistrer_modele(session, autre)


# --- create_db ------------------------------------------------------------------------


def test_create_db_affiche_le_sql(capsys):
    assert main(["--sql"]) == 0
    assert "CREATE TABLE predictions" in capsys.readouterr().out


def test_create_db_ecrit_le_fichier_sql(tmp_path):
    fichier = tmp_path / "schema.sql"
    assert main(["--sql", str(fichier)]) == 0
    assert fichier.read_text(encoding="utf-8") == ddl_postgresql()


def test_create_db_sans_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    assert main([]) == 1


def test_create_db_roles_sans_mot_de_passe(monkeypatch, url_base):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ADMIN_DATABASE_URL", url_base)
    assert main(["--roles"]) == 1


def test_create_db_utilise_le_compte_proprietaire(monkeypatch, tmp_path):
    # DATABASE_URL (compte de l'API) pointe ailleurs : seule l'URL admin doit servir.
    url = f"sqlite:///{tmp_path / 'admin.db'}"
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("ADMIN_DATABASE_URL", url)
    assert main([]) == 0
    assert (tmp_path / "admin.db").exists()
    assert not (tmp_path / "api.db").exists()


def test_create_db_cree_les_tables(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'neuve.db'}"
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", url)
    assert main([]) == 0
    moteur = creer_moteur(url)
    assert set(inspect(moteur).get_table_names()) == {
        "employes",
        "modeles",
        "entrees",
        "predictions",
    }
    moteur.dispose()


def test_create_db_reinitialiser_vide_les_tables(monkeypatch, url_base, modele):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", url_base)
    moteur = creer_moteur(url_base)
    with Session(moteur) as session:
        enregistrer_modele(session, modele)
        enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.5, modele, source="script")
    assert main(["--reinitialiser"]) == 0
    with Session(moteur) as session:
        assert lister_predictions(session, 10) == []
    moteur.dispose()
