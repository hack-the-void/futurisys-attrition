"""Calcul des 44 variables du modèle à partir des 25 champs RH (repris du projet 4)."""

import numpy as np
import pandas as pd

ORDRE_DEPLACEMENT = {"Aucun": 0, "Occasionnel": 1, "Frequent": 2}
COLONNES_ONEHOT = ["statut_marital", "poste", "domaine_etude"]
SATISFACTIONS = [
    "satisfaction_employee_environnement",
    "satisfaction_employee_nature_travail",
    "satisfaction_employee_equipe",
    "satisfaction_employee_equilibre_pro_perso",
]


def construire_features(brut: pd.DataFrame, medianes_salaire_poste: dict, colonnes: list):
    df = brut.copy()

    df["satisfaction_moyenne"] = df[SATISFACTIONS].mean(axis=1)
    df["annees_par_employeur"] = df["annee_experience_totale"] / (
        df["nombre_experiences_precedentes"] + 1
    )
    df["part_carriere_technova"] = (
        (df["annees_dans_l_entreprise"] / df["annee_experience_totale"].replace(0, np.nan))
        .fillna(1.0)
        .clip(upper=1.0)
    )
    # Médianes figées à l'entraînement : sur un seul employé, la médiane serait son salaire.
    df["ratio_salaire_mediane_poste"] = df["revenu_mensuel"] / df["poste"].map(
        medianes_salaire_poste
    )

    df["genre"] = (df["genre"] == "M").astype(int)
    df["heure_supplementaires"] = df["heure_supplementaires"].astype(int)
    df["frequence_deplacement"] = df["frequence_deplacement"].map(ORDRE_DEPLACEMENT)
    df = pd.get_dummies(df, columns=COLONNES_ONEHOT, dtype=int)

    return df.reindex(columns=list(colonnes), fill_value=0).astype(float)
