"""Chargement du dataset du projet 4 et insertion dans PostgreSQL.

Les trois extraits CSV (SIRH, évaluations, sondage) restent hors du dépôt. Ce module les
rapproche comme le projet 4 et les insère dans la table `employes`.
"""

from collections.abc import Collection
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from attrition_api.db import EmployeDataset

CIBLE = "a_quitte_l_entreprise"


def charger_donnees_brutes(dossier: Path) -> pd.DataFrame:
    """Rapproche les trois extraits comme `charger_donnees_centrales` du projet 4.

    Toutes les colonnes sont gardées, y compris celles que le modèle n'utilise pas.
    """
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


def importer_employes(session: Session, brut: pd.DataFrame, ids_test: Collection[int]) -> int:
    """Insère ou met à jour les employés du dataset. Renvoie le nombre de lignes.

    Aucune prédiction n'est calculée ici : c'est l'utilisateur qui demande à l'API la
    prédiction d'un employé. Un nouvel import garde donc les prédictions déjà faites.
    """
    ids_test = set(ids_test)
    # Les employés déjà en base sont chargés en une requête, puis mis à jour par merge.
    session.scalars(select(EmployeDataset)).all()
    # astype(object) donne des types Python natifs, attendus par le pilote de la base.
    for id_employee, ligne in brut.astype(object).iterrows():
        donnees = ligne.to_dict() | {CIBLE: bool(ligne[CIBLE])}
        jeu = "test" if id_employee in ids_test else "train"
        session.merge(EmployeDataset(id=int(id_employee), jeu=jeu, **donnees))
    session.commit()
    return len(brut)
