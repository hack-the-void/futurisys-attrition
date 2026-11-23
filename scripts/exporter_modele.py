"""Exporte le modèle du projet 4 sans les données RH.

L'artefact d'origine (`artefacts/modele_final.joblib`) contient aussi X_train, X_test, y_train
et y_test. Ce script n'en garde que l'estimateur, fige le seuil et les médianes de salaire par
poste, et décrit le tout dans un fichier JSON lisible.

Avant d'écrire, il vérifie que `attrition_api.features` reconstruit exactement les variables
d'entraînement et de test à partir des trois extraits CSV, et que les résultats du test sont
inchangés.

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

from attrition_api.features import construire_features
from attrition_api.modele import DOSSIER_ARTEFACTS, FICHIER_METADONNEES, FICHIER_MODELE

RACINE = Path(__file__).resolve().parents[1]
FICHIER_EXEMPLES = RACINE / "tests" / "donnees" / "exemples_reference.json"
VERSION_MODELE = "1.0.0"
CIBLE = "a_quitte_l_entreprise"
FICHIERS_DONNEES = ["extrait_sirh.csv", "extrait_eval.csv", "extrait_sondage.csv"]

# Profils fictifs : ils servent d'exemples dans les tests et ne viennent pas des données RH.
EXEMPLES_FICTIFS = {
    "profil_a_risque": {
        "age": 26,
        "genre": "M",
        "revenu_mensuel": 2300,
        "statut_marital": "Célibataire",
        "poste": "Représentant Commercial",
        "nombre_experiences_precedentes": 4,
        "annee_experience_totale": 5,
        "annees_dans_l_entreprise": 1,
        "annees_dans_le_poste_actuel": 1,
        "satisfaction_employee_environnement": 1,
        "note_evaluation_precedente": 2,
        "satisfaction_employee_nature_travail": 1,
        "satisfaction_employee_equipe": 2,
        "satisfaction_employee_equilibre_pro_perso": 1,
        "note_evaluation_actuelle": 3,
        "heure_supplementaires": True,
        "augementation_salaire_precedente": 11,
        "nombre_participation_pee": 0,
        "nb_formations_suivies": 1,
        "distance_domicile_travail": 24,
        "niveau_education": 2,
        "domaine_etude": "Marketing",
        "frequence_deplacement": "Frequent",
        "annees_depuis_la_derniere_promotion": 0,
        "annes_sous_responsable_actuel": 0,
    },
    "profil_stable": {
        "age": 45,
        "genre": "F",
        "revenu_mensuel": 9800,
        "statut_marital": "Marié(e)",
        "poste": "Manager",
        "nombre_experiences_precedentes": 1,
        "annee_experience_totale": 20,
        "annees_dans_l_entreprise": 15,
        "annees_dans_le_poste_actuel": 7,
        "satisfaction_employee_environnement": 4,
        "note_evaluation_precedente": 3,
        "satisfaction_employee_nature_travail": 4,
        "satisfaction_employee_equipe": 3,
        "satisfaction_employee_equilibre_pro_perso": 3,
        "note_evaluation_actuelle": 3,
        "heure_supplementaires": False,
        "augementation_salaire_precedente": 15,
        "nombre_participation_pee": 2,
        "nb_formations_suivies": 3,
        "distance_domicile_travail": 5,
        "niveau_education": 4,
        "domaine_etude": "Infra & Cloud",
        "frequence_deplacement": "Occasionnel",
        "annees_depuis_la_derniere_promotion": 2,
        "annes_sous_responsable_actuel": 6,
    },
    "premier_emploi": {
        "age": 18,
        "genre": "F",
        "revenu_mensuel": 1500,
        "statut_marital": "Célibataire",
        "poste": "Consultant",
        "nombre_experiences_precedentes": 0,
        "annee_experience_totale": 0,
        "annees_dans_l_entreprise": 0,
        "annees_dans_le_poste_actuel": 0,
        "satisfaction_employee_environnement": 3,
        "note_evaluation_precedente": 3,
        "satisfaction_employee_nature_travail": 3,
        "satisfaction_employee_equipe": 3,
        "satisfaction_employee_equilibre_pro_perso": 3,
        "note_evaluation_actuelle": 3,
        "heure_supplementaires": False,
        "augementation_salaire_precedente": 13,
        "nombre_participation_pee": 0,
        "nb_formations_suivies": 2,
        "distance_domicile_travail": 10,
        "niveau_education": 1,
        "domaine_etude": "Autre",
        "frequence_deplacement": "Aucun",
        "annees_depuis_la_derniere_promotion": 0,
        "annes_sous_responsable_actuel": 0,
    },
}


def sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def charger_donnees_brutes(dossier: Path) -> pd.DataFrame:
    """Rapproche les trois extraits comme `charger_donnees_centrales` du projet 4."""
    sirh = pd.read_csv(dossier / "extrait_sirh.csv")
    evals = pd.read_csv(dossier / "extrait_eval.csv")
    sondage = pd.read_csv(dossier / "extrait_sondage.csv", dtype={"code_sondage": str})

    evals["id_employee"] = evals.pop("eval_number").str.split("_").str[-1].astype(int)
    evals["heure_supplementaires"] = evals["heure_supplementaires"].str.strip().eq("Oui")
    evals["augementation_salaire_precedente"] = (
        evals["augementation_salaire_precedente"].str.replace("%", "").str.strip().astype(float)
    )
    sondage["id_employee"] = sondage.pop("code_sondage").astype(int)
    sondage[CIBLE] = sondage[CIBLE].str.strip().eq("Oui").astype(int)

    return (
        sirh.merge(evals, on="id_employee", validate="one_to_one")
        .merge(sondage, on="id_employee", validate="one_to_one")
        .set_index("id_employee")
        .sort_index()
    )


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
    )

    exemples = pd.DataFrame.from_dict(EXEMPLES_FICTIFS, orient="index")
    probas = modele.predict_proba(construire_features(exemples, medianes, colonnes))[:, 1]
    FICHIER_EXEMPLES.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_EXEMPLES.write_text(
        json.dumps(
            {
                nom: {"entree": entree, "probabilite_attendue": float(p)}
                for (nom, entree), p in zip(EXEMPLES_FICTIFS.items(), probas, strict=True)
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Artefact écrit dans {DOSSIER_ARTEFACTS.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
