import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from attrition_api.acces import configurer_acces
from attrition_api.db import creer_moteur, enregistrer_modele, enregistrer_prediction
from attrition_api.modele import charger_modele
from attrition_api.schemas import EXEMPLE_EMPLOYE

# Un rôle propre aux tests, pour ne pas changer le mot de passe du vrai rôle de l'API.
ROLE_TEST = "api_attrition_test"
MOT_DE_PASSE = "mot-de-passe-de-test"
URL_TEST = os.environ.get("TEST_DATABASE_URL")
sous_postgresql = pytest.mark.skipif(
    URL_TEST is None or make_url(URL_TEST).get_backend_name() != "postgresql",
    reason="Les rôles n'existent que sous PostgreSQL (TEST_DATABASE_URL)",
)


def test_refuse_hors_postgresql(tmp_path):
    moteur = creer_moteur(f"sqlite:///{tmp_path / 'base.db'}")
    with pytest.raises(ValueError, match="PostgreSQL"):
        configurer_acces(moteur, MOT_DE_PASSE)


@pytest.fixture
def moteur_api(url_base):
    """Base avec une prédiction, et un moteur connecté avec le rôle de l'API."""
    admin = creer_moteur(url_base)
    modele = charger_modele()
    with Session(admin) as session:
        enregistrer_modele(session, modele)
        enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.5, modele, source="api")
    # Deux passages : le second met à jour un rôle qui existe déjà.
    configurer_acces(admin, "ancien-mot-de-passe", role_api=ROLE_TEST)
    configurer_acces(admin, MOT_DE_PASSE, role_api=ROLE_TEST)
    admin.dispose()

    url = make_url(url_base).set(username=ROLE_TEST, password=MOT_DE_PASSE)
    moteur = creer_moteur(url.render_as_string(hide_password=False))
    yield moteur
    moteur.dispose()


@sous_postgresql
def test_le_role_de_l_api_peut_lire_et_ajouter(moteur_api):
    modele = charger_modele()
    with Session(moteur_api) as session:
        ligne = enregistrer_prediction(session, EXEMPLE_EMPLOYE, 0.9, modele, source="api")
        assert ligne.id is not None
        assert session.scalar(text("SELECT COUNT(*) FROM predictions")) == 2


@sous_postgresql
@pytest.mark.parametrize(
    "requete",
    [
        "DELETE FROM predictions",
        "UPDATE predictions SET probabilite = 0",
        "SELECT * FROM employes",
        "DROP TABLE predictions",
        "CREATE TABLE intrusion (id int)",
    ],
)
def test_le_role_de_l_api_ne_peut_rien_d_autre(moteur_api, requete):
    with (
        moteur_api.connect() as connexion,
        pytest.raises(ProgrammingError, match="permission|owner"),
    ):
        connexion.execute(text(requete))
