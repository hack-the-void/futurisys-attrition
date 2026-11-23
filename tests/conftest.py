import json
import os
from pathlib import Path

import pytest

from attrition_api.create_db import creer_tables
from attrition_api.db import creer_moteur

DOSSIER_DONNEES = Path(__file__).resolve().parent / "donnees"
# En CI, TEST_DATABASE_URL pointe vers un service PostgreSQL. Sinon, SQLite suffit en local.
URL_BASE_TEST = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def environnement_isole(monkeypatch, tmp_path):
    # Les tests partent d'un dossier vide et définissent leurs propres variables.
    for variable in ("APP_ENV", "API_KEY", "DATABASE_URL"):
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
