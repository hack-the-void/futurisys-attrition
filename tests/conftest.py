import json
import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from attrition_api.create_db import creer_tables
from attrition_api.db import creer_moteur

DOSSIER_DONNEES = Path(__file__).resolve().parent / "donnees"
# Trois employés fictifs au format des extraits RH, sur les profils de exemples_reference.json.
DOSSIER_SOURCES = DOSSIER_DONNEES / "sources"
# En CI, TEST_DATABASE_URL pointe vers un service PostgreSQL. Sinon, SQLite suffit en local.
URL_BASE_TEST = os.environ.get("TEST_DATABASE_URL")
VARIABLES = (
    "APP_ENV",
    "API_KEY",
    "DATABASE_URL",
    "ADMIN_DATABASE_URL",
    "API_DB_PASSWORD",
)

sous_postgresql = pytest.mark.skipif(
    URL_BASE_TEST is None or make_url(URL_BASE_TEST).get_backend_name() != "postgresql",
    reason="Rôles et droits : nécessite TEST_DATABASE_URL vers PostgreSQL",
)


@pytest.fixture(autouse=True)
def environnement_isole(monkeypatch, tmp_path):
    # Les tests partent d'un dossier vide et définissent leurs propres variables.
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="session")
def exemples():
    """Profils fictifs et probabilités calculées par scripts/exporter_modele.py."""
    return json.loads((DOSSIER_DONNEES / "exemples_reference.json").read_text(encoding="utf-8"))


@pytest.fixture
def url_base(tmp_path):
    """URL d'une base dont les tables viennent d'être recréées, vides."""
    url = URL_BASE_TEST or f"sqlite:///{tmp_path / 'test.db'}"
    moteur = creer_moteur(url)
    creer_tables(moteur, reinitialiser=True)
    moteur.dispose()
    return url
