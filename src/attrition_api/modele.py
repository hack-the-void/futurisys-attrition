"""Chargement de l'artefact et calcul des probabilités de départ."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from attrition_api.features import construire_features

DOSSIER_ARTEFACTS = Path(__file__).resolve().parent / "artefacts"
FICHIER_MODELE = DOSSIER_ARTEFACTS / "modele_attrition.joblib"
FICHIER_METADONNEES = DOSSIER_ARTEFACTS / "modele_attrition.json"


class ArtefactInvalide(RuntimeError):
    """Le fichier du modèle ne correspond pas à ses métadonnées."""


@dataclass(frozen=True)
class ModeleAttrition:
    estimateur: Any
    metadonnees: dict[str, Any]

    @property
    def version(self) -> str:
        return self.metadonnees["version"]

    @property
    def seuil(self) -> float:
        return self.metadonnees["seuil"]

    def predire(self, employes: Sequence[Mapping[str, Any]]) -> list[float]:
        """Renvoie la probabilité de départ de chaque employé, dans l'ordre reçu."""
        X = construire_features(
            pd.DataFrame(list(employes)),
            self.metadonnees["medianes_salaire_poste"],
            self.metadonnees["colonnes"],
        )
        # Le modèle accepte les valeurs manquantes : une erreur d'entrée passerait inaperçue.
        if X.isna().any().any():
            manquantes = X.columns[X.isna().any()].tolist()
            raise ValueError(f"Variables non calculables : {manquantes}")
        return self.estimateur.predict_proba(X)[:, 1].tolist()


def charger_modele(
    fichier_modele: Path = FICHIER_MODELE, fichier_metadonnees: Path = FICHIER_METADONNEES
) -> ModeleAttrition:
    """Charge le modèle après avoir vérifié son empreinte.

    joblib exécute du code au chargement : on n'ouvre que le fichier dont l'empreinte SHA-256
    correspond à celle enregistrée à l'export.
    """
    metadonnees = json.loads(fichier_metadonnees.read_text(encoding="utf-8"))
    empreinte = hashlib.sha256(fichier_modele.read_bytes()).hexdigest()
    if empreinte != metadonnees["sha256_modele"]:
        raise ArtefactInvalide(f"Empreinte inattendue pour {fichier_modele.name}")
    return ModeleAttrition(joblib.load(fichier_modele), metadonnees)
