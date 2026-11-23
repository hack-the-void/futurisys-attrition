"""Exporte le modèle du projet 4 sans les données RH.

L'artefact d'origine (`artefacts/modele_final.joblib`) contient aussi X_train, X_test, y_train
et y_test. Ce script n'en garde que l'estimateur, fige le seuil et les médianes de salaire par
poste, et décrit le tout dans un fichier JSON lisible.

Avant d'écrire, il vérifie que `attrition_api.features` reconstruit exactement les variables
d'entraînement et de test à partir des trois extraits CSV, et que les résultats du test sont
inchangés. Il écrit aussi les trois employés de référence utilisés par les tests.

Usage :
    uv run python scripts/exporter_modele.py --source ../../technova-attrition
"""

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)

from attrition_api.dataset import charger_donnees_brutes
from attrition_api.features import construire_features
from attrition_api.modele import DOSSIER_ARTEFACTS, FICHIER_METADONNEES, FICHIER_MODELE
from attrition_api.schemas import Employe

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_TESTS = RACINE / "tests" / "donnees"
FICHIER_EXEMPLES = DOSSIER_TESTS / "exemples_reference.json"
VERSION_MODELE = "1.0.0"
FICHIERS_DONNEES = ["extrait_sirh.csv", "extrait_eval.csv", "extrait_sondage.csv"]

# Employés du jeu de test utilisés comme références dans les tests.
EMPLOYES_REFERENCE = {"depart": 478, "stable": 734, "premier_emploi": 1839}


def sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def resultats_test(y, probas, seuil: float) -> dict:
    pred = (probas >= seuil).astype(int)
    vn, fp, fn, vp = confusion_matrix(y, pred).ravel()
    return {
        "effectif": int(len(y)),
        "departs": int(y.sum()),
        "precision": round(float(precision_score(y, pred)), 4),
        "rappel": round(float(recall_score(y, pred)), 4),
        "f1": round(float(f1_score(y, pred)), 4),
        "f2": round(float(fbeta_score(y, pred, beta=2)), 4),
        "pr_auc": round(float(average_precision_score(y, probas)), 4),
        "matrice_confusion": {"vn": int(vn), "fp": int(fp), "fn": int(fn), "vp": int(vp)},
    }


def en_json(valeur):
    if isinstance(valeur, np.generic):
        return valeur.item()
    raise TypeError(f"Type non sérialisable : {type(valeur)}")


def ecrire_exemples(brut, modele, medianes, colonnes, ids_test):
    ids = list(EMPLOYES_REFERENCE.values())
    assert ids_test.issuperset(ids), "Les employés de référence doivent venir du jeu de test"
    entrees = brut.loc[ids, list(Employe.model_fields)].astype(object)
    probas = modele.predict_proba(construire_features(entrees, medianes, colonnes))[:, 1]
    exemples = {
        nom: {
            "id_employee": id_employee,
            "a_quitte_l_entreprise": bool(brut.loc[id_employee, "a_quitte_l_entreprise"]),
            "entree": Employe(**entrees.loc[id_employee].to_dict()).model_dump(),
            "probabilite_attendue": float(p),
        }
        for (nom, id_employee), p in zip(EMPLOYES_REFERENCE.items(), probas, strict=True)
    }
    FICHIER_EXEMPLES.write_text(
        json.dumps(exemples, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extraire_sources(dossier: Path, ids: list[int]):
    # Les lignes brutes de ces employés, pour tester le chargement des trois CSV.
    cles = {
        "extrait_sirh.csv": "id_employee",
        "extrait_eval.csv": "eval_number",
        "extrait_sondage.csv": "code_sondage",
    }
    for fichier, colonne in cles.items():
        df = pd.read_csv(dossier / fichier, dtype=str)
        id_employee = df[colonne].str.split("_").str[-1].astype(int)
        lignes = df[id_employee.isin(ids)]
        lignes.to_csv(DOSSIER_TESTS / "sources" / fichier, index=False, lineterminator="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="Dossier du projet 4")
    args = parser.parse_args()

    chemin_source = args.source / "artefacts" / "modele_final.joblib"
    source = joblib.load(chemin_source)
    modele, seuil = source["modele"], float(source["seuil"])
    colonnes = list(modele.feature_names_in_)

    brut = charger_donnees_brutes(args.source / "data")
    # Comme dans le projet 4, les médianes viennent de toute la base, test compris.
    medianes = brut.groupby("poste")["revenu_mensuel"].median().to_dict()

    X = construire_features(brut, medianes, colonnes)
    for nom in ("X_train", "X_test"):
        attendu = source[nom]
        pd.testing.assert_frame_equal(X.loc[attendu.index], attendu, check_dtype=False)
    print("Variables reconstruites identiques à X_train et X_test.")

    probas_test = modele.predict_proba(source["X_test"])[:, 1]
    resultats = resultats_test(source["y_test"], probas_test, seuil)
    print(f"Résultats du test : {resultats}")

    DOSSIER_ARTEFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, FICHIER_MODELE)

    metadonnees = {
        "version": VERSION_MODELE,
        "date_export": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithme": type(modele).__name__,
        "hyperparametres": modele.get_params(),
        "seuil": seuil,
        "colonnes": colonnes,
        "medianes_salaire_poste": medianes,
        "resultats_test": resultats,
        "versions": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "source": {
            "artefact": chemin_source.name,
            "sha256": sha256(chemin_source),
            "commit_entrainement": None,  # Le projet 4 n'est pas versionné avec Git.
            "donnees": {f: sha256(args.source / "data" / f) for f in FICHIERS_DONNEES},
        },
        "sha256_modele": sha256(FICHIER_MODELE),
    }
    FICHIER_METADONNEES.write_text(
        json.dumps(metadonnees, ensure_ascii=False, indent=2, default=en_json) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    ecrire_exemples(brut, modele, medianes, colonnes, set(source["X_test"].index))
    extraire_sources(args.source / "data", sorted(EMPLOYES_REFERENCE.values()))
    print(f"Artefact écrit dans {DOSSIER_ARTEFACTS.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
