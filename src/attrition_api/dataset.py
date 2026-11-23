"""Chargement du dataset du projet 4 et insertion dans PostgreSQL.

Les trois extraits CSV (SIRH, évaluations, sondage) restent hors du dépôt. Ce module les
rapproche comme le projet 4, les insère dans la table `employes`, puis fait passer chaque
employé par le modèle en enregistrant les entrées et les prédictions.
"""

from collections.abc import Collection
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from attrition_api.db import (
    EmployeDataset,
    Entree,
    PredictionEnregistree,
    enregistrer_modele,
    enregistrer_prediction,
)
from attrition_api.modele import ModeleAttrition
from attrition_api.schemas import Employe

CIBLE = "a_quitte_l_entreprise"
SOURCE_DATASET = "dataset"


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


def supprimer_dataset(session: Session) -> None:
    """Retire les employés du dataset, leurs entrées et leurs prédictions."""
    entrees_dataset = select(Entree.id).where(Entree.source == SOURCE_DATASET)
    # Suppression explicite : SQLite n'applique pas ON DELETE CASCADE par défaut.
    session.execute(
        delete(PredictionEnregistree).where(PredictionEnregistree.entree_id.in_(entrees_dataset))
    )
    session.execute(delete(Entree).where(Entree.source == SOURCE_DATASET))
    session.execute(delete(EmployeDataset))


def importer_employes(session: Session, brut: pd.DataFrame, ids_test: Collection[int]) -> int:
    """Remplace le contenu de `employes` par le dataset. Renvoie le nombre de lignes."""
    supprimer_dataset(session)
    ids_test = set(ids_test)
    lignes = []
    # astype(object) donne des types Python natifs, attendus par le pilote de la base.
    for id_employee, ligne in brut.astype(object).iterrows():
        donnees = ligne.to_dict() | {CIBLE: bool(ligne[CIBLE])}
        jeu = "test" if id_employee in ids_test else "train"
        lignes.append(EmployeDataset(id=int(id_employee), jeu=jeu, **donnees))
    session.add_all(lignes)
    session.commit()
    return len(lignes)


def predire_dataset(session: Session, modele: ModeleAttrition) -> int:
    """Fait passer chaque employé du dataset par le modèle et enregistre le résultat.

    Les champs sont validés par le même schéma que l'API, puis les entrées et les
    prédictions sont écrites dans une seule transaction.
    """
    enregistrer_modele(session, modele)
    employes = session.scalars(select(EmployeDataset).order_by(EmployeDataset.id)).all()
    entrees = [
        Employe(**{champ: getattr(e, champ) for champ in Employe.model_fields}).model_dump()
        for e in employes
    ]
    probabilites = modele.predire(entrees)
    for employe, entree, probabilite in zip(employes, entrees, probabilites, strict=True):
        enregistrer_prediction(
            session,
            entree,
            probabilite,
            modele,
            source=SOURCE_DATASET,
            employe_id=employe.id,
            valider=False,
        )
    session.commit()
    return len(employes)
