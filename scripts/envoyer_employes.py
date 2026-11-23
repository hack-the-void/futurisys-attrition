"""Envoie des employés à l'API, qui calcule et enregistre chaque prédiction.

La clé est lue dans API_KEY (variable d'environnement ou fichier .env).

Usage :
    uv run python scripts/envoyer_employes.py db/exemples/employes_fictifs.csv
    uv run python scripts/envoyer_employes.py employes.csv --url http://127.0.0.1:8000
"""

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from attrition_api.config import Settings
from attrition_api.schemas import Employe


def envoyer(url: str, cle: str, employe: Employe) -> dict:
    requete = urllib.request.Request(
        f"{url}/predictions",
        data=employe.model_dump_json().encode(),
        headers={"Content-Type": "application/json", "X-API-Key": cle},
        method="POST",
    )
    with urllib.request.urlopen(requete, timeout=10) as reponse:
        return json.load(reponse)


def main() -> int:
    parser = argparse.ArgumentParser(description="Envoie un CSV d'employés à l'API.")
    parser.add_argument("fichier", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    settings = Settings()
    if settings.api_key is None:
        print("API_KEY n'est pas définie.", file=sys.stderr)
        return 1
    cle = settings.api_key.get_secret_value()

    with args.fichier.open(encoding="utf-8", newline="") as fichier:
        # La validation locale convertit les textes du CSV et écarte les lignes invalides.
        employes = [Employe(**ligne) for ligne in csv.DictReader(fichier)]

    alertes = 0
    for numero, employe in enumerate(employes, start=1):
        try:
            prediction = envoyer(args.url, cle, employe)
        except urllib.error.HTTPError as erreur:
            print(f"Ligne {numero} : erreur {erreur.code} {erreur.read().decode()}")
            return 1
        alertes += prediction["risque_depart"]
        print(
            f"Ligne {numero} -> prédiction {prediction['id_prediction']} : "
            f"{prediction['probabilite_depart']:.1%}"
            + (" (alerte)" if prediction["risque_depart"] else "")
        )
    print(f"{len(employes)} prédictions enregistrées, dont {alertes} alertes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
