import tomllib
from pathlib import Path

import attrition_api

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_version_du_paquet_identique_a_pyproject():
    projet = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert attrition_api.__version__ == projet["version"]
