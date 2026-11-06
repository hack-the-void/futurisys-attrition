import pytest


@pytest.fixture(autouse=True)
def environnement_isole(monkeypatch, tmp_path):
    # Les tests partent d'un dossier vide et définissent leurs propres variables.
    for variable in ("APP_ENV", "API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(tmp_path)
