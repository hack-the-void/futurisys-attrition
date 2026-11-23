from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from attrition_api.dataset import charger_donnees_brutes, importer_employes
from attrition_api.db import Entree, ModeleEnregistre, PredictionEnregistree, creer_moteur
from attrition_api.main import app
from attrition_api.schemas import EXEMPLE_EMPLOYE

DOSSIER_SOURCES = Path(__file__).resolve().parents[1] / "donnees" / "sources"
CLE_TEST = "cle-de-test-pour-les-appels-a-l-api"
EN_TETES = {"X-API-Key": CLE_TEST}


@pytest.fixture
def client(monkeypatch, url_base):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("API_KEY", CLE_TEST)
    monkeypatch.setenv("DATABASE_URL", url_base)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def session(url_base):
    moteur = creer_moteur(url_base)
    with Session(moteur) as session:
        yield session
    moteur.dispose()


@pytest.fixture
def employes(session):
    """Les employés 478, 734 et 1839 dans la table employes."""
    importer_employes(session, charger_donnees_brutes(DOSSIER_SOURCES), ids_test={478})


def predire(client, employe=EXEMPLE_EMPLOYE):
    reponse = client.post("/predictions", headers=EN_TETES, json=employe)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


# --- Service et documentation ---------------------------------------------------------


def test_health_sans_authentification(client):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "version_api": app.version, "version_modele": "1.0.0"}


def test_documentation_openapi(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert {
        "/health",
        "/modele",
        "/employes",
        "/employes/{id_employe}",
        "/employes/{id_employe}/predictions",
        "/predictions",
        "/predictions/{id_prediction}",
    } <= set(schema["paths"])
    assert "APIKeyHeader" in schema["components"]["securitySchemes"]


def test_modele_enregistre_au_demarrage(client, session):
    modele = session.get(ModeleEnregistre, "1.0.0")
    assert modele.algorithme == "HistGradientBoostingClassifier"
    assert modele.resultats_test["matrice_confusion"]["vp"] == 33


# --- Authentification -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("methode", "route"),
    [
        ("get", "/modele"),
        ("get", "/employes"),
        ("get", "/employes/478"),
        ("post", "/employes/478/predictions"),
        ("post", "/predictions"),
        ("get", "/predictions"),
        ("get", "/predictions/1"),
    ],
)
@pytest.mark.parametrize("en_tetes", [{}, {"X-API-Key": "mauvaise-cle"}])
def test_cle_absente_ou_invalide_refusee(client, methode, route, en_tetes):
    reponse = client.request(methode, route, headers=en_tetes, json=EXEMPLE_EMPLOYE)
    assert reponse.status_code == 401
    assert reponse.headers["WWW-Authenticate"] == "APIKey"


def test_cle_non_configuree(monkeypatch, url_base):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", url_base)
    with TestClient(app) as client:
        reponse = client.post("/predictions", headers=EN_TETES, json=EXEMPLE_EMPLOYE)
    assert reponse.status_code == 503


def test_appel_refuse_n_est_pas_enregistre(client, session):
    client.post("/predictions", json=EXEMPLE_EMPLOYE)
    assert session.scalar(select(func.count()).select_from(Entree)) == 0


# --- Modèle et prédictions ------------------------------------------------------------


def test_infos_modele(client):
    reponse = client.get("/modele", headers=EN_TETES)
    assert reponse.status_code == 200
    infos = reponse.json()
    assert infos["algorithme"] == "HistGradientBoostingClassifier"
    assert len(infos["variables"]) == 44
    assert infos["resultats_test"]["rappel"] == pytest.approx(0.70, abs=0.01)


@pytest.mark.parametrize(
    ("profil", "risque_attendu"),
    [("depart", True), ("stable", False), ("premier_emploi", True)],
)
def test_prediction(client, exemples, profil, risque_attendu):
    exemple = exemples[profil]
    prediction = predire(client, exemple["entree"])
    assert prediction["probabilite_depart"] == pytest.approx(exemple["probabilite_attendue"])
    assert prediction["risque_depart"] is risque_attendu
    assert prediction["seuil"] == pytest.approx(0.4453, abs=1e-4)
    assert prediction["version_modele"] == "1.0.0"


def test_prediction_enregistree_en_base(client, session):
    prediction = predire(client)
    ligne = session.get(PredictionEnregistree, prediction["id_prediction"])
    assert ligne.probabilite == pytest.approx(prediction["probabilite_depart"])
    assert ligne.risque_depart is True
    assert ligne.entree.source == "api"
    assert ligne.entree.poste == EXEMPLE_EMPLOYE["poste"]


def test_relire_une_prediction(client):
    prediction = predire(client)
    reponse = client.get(f"/predictions/{prediction['id_prediction']}", headers=EN_TETES)
    assert reponse.status_code == 200
    detail = reponse.json()
    assert detail["entree"] == EXEMPLE_EMPLOYE
    assert detail["probabilite_depart"] == pytest.approx(prediction["probabilite_depart"])


def test_prediction_introuvable(client):
    reponse = client.get("/predictions/999999", headers=EN_TETES)
    assert reponse.status_code == 404


def test_lister_les_dernieres_predictions(client, exemples):
    ids = [predire(client, e["entree"])["id_prediction"] for e in exemples.values()]
    reponse = client.get("/predictions", headers=EN_TETES, params={"limite": 2})
    assert reponse.status_code == 200
    assert [p["id_prediction"] for p in reponse.json()] == ids[::-1][:2]


@pytest.mark.parametrize("limite", [0, 101])
def test_limite_hors_bornes(client, limite):
    reponse = client.get("/predictions", headers=EN_TETES, params={"limite": limite})
    assert reponse.status_code == 422


@pytest.mark.parametrize(
    "corps",
    [
        EXEMPLE_EMPLOYE | {"poste": "Stagiaire"},
        EXEMPLE_EMPLOYE | {"annees_dans_l_entreprise": 30},
        {"age": 30},
        [],
    ],
)
def test_entree_invalide_ni_predite_ni_enregistree(client, session, corps):
    reponse = client.post("/predictions", headers=EN_TETES, json=corps)
    assert reponse.status_code == 422
    assert session.scalar(select(func.count()).select_from(Entree)) == 0


# --- Employés de la base -------------------------------------------------------------


def test_lister_les_employes(client, employes):
    reponse = client.get("/employes", headers=EN_TETES)
    assert reponse.status_code == 200
    assert [e["id"] for e in reponse.json()] == [478, 734, 1839]
    assert reponse.json()[0] == {
        "id": 478,
        "age": 21,
        "genre": "F",
        "departement": "Commercial",
        "poste": "Représentant Commercial",
    }


@pytest.mark.parametrize(
    ("params", "ids"),
    [
        ({"limite": 1, "decalage": 1}, [734]),
        ({"poste": "Représentant Commercial"}, [478]),
        ({"departement": "Inconnu"}, []),
    ],
)
def test_filtrer_les_employes(client, employes, params, ids):
    reponse = client.get("/employes", headers=EN_TETES, params=params)
    assert [e["id"] for e in reponse.json()] == ids


def test_fiche_employe_sans_son_depart_reel(client, employes):
    reponse = client.get("/employes/478", headers=EN_TETES)
    assert reponse.status_code == 200
    fiche = reponse.json()
    assert fiche == {"id": 478, "departement": "Commercial"} | EXEMPLE_EMPLOYE
    assert "a_quitte_l_entreprise" not in fiche


@pytest.mark.parametrize("nom", ["depart", "stable", "premier_emploi"])
def test_prediction_d_un_employe_choisi(client, session, employes, exemples, nom):
    exemple = exemples[nom]
    id_employe = exemple["id_employee"]
    assert session.scalar(select(func.count()).select_from(PredictionEnregistree)) == 0

    reponse = client.post(f"/employes/{id_employe}/predictions", headers=EN_TETES)

    assert reponse.status_code == 201, reponse.text
    prediction = reponse.json()
    assert prediction["id_employe"] == id_employe
    assert prediction["probabilite_depart"] == pytest.approx(exemple["probabilite_attendue"])
    ligne = session.get(PredictionEnregistree, prediction["id_prediction"])
    assert (ligne.entree.employe_id, ligne.entree.source) == (id_employe, "api")


def test_chaque_choix_est_une_nouvelle_prediction(client, employes):
    ids = {
        client.post("/employes/478/predictions", headers=EN_TETES).json()["id_prediction"]
        for _ in range(2)
    }
    assert len(ids) == 2


@pytest.mark.parametrize(
    ("methode", "route"), [("get", "/employes/1"), ("post", "/employes/1/predictions")]
)
def test_employe_introuvable(client, session, employes, methode, route):
    reponse = client.request(methode, route, headers=EN_TETES)
    assert reponse.status_code == 404
    assert session.scalar(select(func.count()).select_from(Entree)) == 0


# --- Démarrage ------------------------------------------------------------------------


def test_demarrage_refuse_en_production_sans_secrets(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ValidationError, match="API_KEY"), TestClient(app):
        pass


def test_demarrage_refuse_sans_base(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    with pytest.raises(RuntimeError, match="DATABASE_URL"), TestClient(app):
        pass


def test_demarrage_refuse_sans_tables(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vide.db'}")
    with pytest.raises(RuntimeError, match="create_db"), TestClient(app):
        pass
