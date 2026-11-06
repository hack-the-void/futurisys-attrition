from pathlib import Path

import pytest
from pydantic import ValidationError

from attrition_api.config import LONGUEUR_MIN_CLE_API, Environnement, Settings, main

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
CLE_VALIDE = "cle-de-test-" + "x" * LONGUEUR_MIN_CLE_API
URL_VALIDE = "postgresql+psycopg://attrition:mdp-de-test@localhost:5432/attrition"


def definir_prod(monkeypatch, api_key=CLE_VALIDE, database_url=URL_VALIDE):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("API_KEY", api_key)
    monkeypatch.setenv("DATABASE_URL", database_url)


@pytest.mark.parametrize("environnement", ["dev", "test"])
def test_secrets_facultatifs_hors_production(monkeypatch, environnement):
    monkeypatch.setenv("APP_ENV", environnement)
    settings = Settings()
    assert settings.app_env == Environnement(environnement)
    assert settings.api_key is None
    assert settings.database_url is None


def test_environnement_obligatoire():
    with pytest.raises(ValidationError, match="app_env"):
        Settings()


def test_environnement_inconnu_refuse(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValidationError, match="app_env"):
        Settings()


def test_production_valide(monkeypatch):
    definir_prod(monkeypatch)
    assert Settings().app_env is Environnement.PROD


@pytest.mark.parametrize(
    ("api_key", "database_url", "champ_en_cause"),
    [
        ("", URL_VALIDE, "API_KEY"),
        ("trop-courte", URL_VALIDE, "API_KEY"),
        ("a-remplacer" + "x" * LONGUEUR_MIN_CLE_API, URL_VALIDE, "API_KEY"),
        (CLE_VALIDE, "", "DATABASE_URL"),
        (CLE_VALIDE, "sqlite:///attrition.db", "DATABASE_URL"),
        (CLE_VALIDE, "postgresql://attrition:a-remplacer@localhost/attrition", "DATABASE_URL"),
    ],
)
def test_production_refuse_les_secrets_invalides(
    monkeypatch, api_key, database_url, champ_en_cause
):
    definir_prod(monkeypatch, api_key=api_key, database_url=database_url)
    with pytest.raises(ValidationError, match=champ_en_cause):
        Settings()


def test_production_refuse_des_secrets_absents(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ValidationError) as erreur:
        Settings()
    assert "API_KEY" in str(erreur.value)
    assert "DATABASE_URL" in str(erreur.value)


def test_le_fichier_env_est_lu(tmp_path):
    (tmp_path / ".env").write_text("APP_ENV=dev\nAPI_KEY=depuis-le-fichier\n", encoding="utf-8")
    settings = Settings()
    assert settings.app_env is Environnement.DEV
    assert settings.api_key.get_secret_value() == "depuis-le-fichier"


def test_env_example_fonctionne_en_dev():
    assert Settings(_env_file=ENV_EXAMPLE).app_env is Environnement.DEV


def test_env_example_est_refuse_en_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(ValidationError):
        Settings(_env_file=ENV_EXAMPLE)


def test_secrets_masques_dans_la_representation(monkeypatch):
    definir_prod(monkeypatch)
    settings = Settings()
    for texte in (repr(settings), str(settings), settings.model_dump_json()):
        assert CLE_VALIDE not in texte
        assert "mdp-de-test" not in texte


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({"API_KEY": CLE_VALIDE, "DATABASE_URL": URL_VALIDE}, id="app_env_absent"),
        pytest.param(
            {"APP_ENV": "prod", "API_KEY": CLE_VALIDE, "DATABASE_URL": "mysql://u:mdp-de-test@h/d"},
            id="url_refusee",
        ),
    ],
)
def test_valeurs_recues_absentes_des_messages_d_erreur(monkeypatch, variables):
    # Pydantic peut tronquer une valeur. Vérifier aussi l'absence du champ input_value.
    for nom, valeur in variables.items():
        monkeypatch.setenv(nom, valeur)
    with pytest.raises(ValidationError) as erreur:
        Settings()
    assert "input_value" not in str(erreur.value)
    assert "mdp-de-test" not in str(erreur.value)


def test_commande_de_controle_configuration_valide(monkeypatch, capsys):
    definir_prod(monkeypatch)
    assert main() == 0
    sortie = capsys.readouterr()
    assert "prod" in sortie.out
    assert CLE_VALIDE not in sortie.out + sortie.err
    assert "mdp-de-test" not in sortie.out + sortie.err


def test_commande_de_controle_configuration_invalide(monkeypatch, capsys):
    definir_prod(monkeypatch, api_key="trop-courte-mais-secrete")
    assert main() == 1
    sortie = capsys.readouterr()
    assert "API_KEY" in sortie.err
    assert "trop-courte-mais-secrete" not in sortie.out + sortie.err
    assert "mdp-de-test" not in sortie.out + sortie.err
