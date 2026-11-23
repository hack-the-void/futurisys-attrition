"""Chargement du modèle et calcul des probabilités de départ."""

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

from attrition_api.features import construire_features

DOSSIER_ARTEFACTS = Path(__file__).resolve().parent / "artefacts"
FICHIER_MODELE = DOSSIER_ARTEFACTS / "modele_attrition.joblib"
FICHIER_METADONNEES = DOSSIER_ARTEFACTS / "modele_attrition.json"


class ArtefactInvalide(RuntimeError):
    pass


class ModeleAttrition:
    def __init__(self, estimateur, metadonnees: dict):
        self.estimateur = estimateur
        self.metadonnees = metadonnees
        self.version = metadonnees["version"]
        self.seuil = metadonnees["seuil"]

    def predire(self, employes: list[dict]) -> list[float]:
        X = construire_features(
            pd.DataFrame(employes),
            self.metadonnees["medianes_salaire_poste"],
            self.metadonnees["colonnes"],
        )
        # Le modèle accepte les NaN sans erreur, donc on vérifie avant.
        if X.isna().any().any():
            manquantes = X.columns[X.isna().any()].tolist()
            raise ValueError(f"Variables non calculables : {manquantes}")
        return self.estimateur.predict_proba(X)[:, 1].tolist()


def charger_modele(fichier_modele=FICHIER_MODELE, fichier_metadonnees=FICHIER_METADONNEES):
    metadonnees = json.loads(Path(fichier_metadonnees).read_text(encoding="utf-8"))
    # joblib exécute du code au chargement : on vérifie d'abord l'empreinte du fichier.
    empreinte = hashlib.sha256(Path(fichier_modele).read_bytes()).hexdigest()
    if empreinte != metadonnees["sha256_modele"]:
        raise ArtefactInvalide(f"Empreinte inattendue pour {Path(fichier_modele).name}")
    return ModeleAttrition(joblib.load(fichier_modele), metadonnees)
