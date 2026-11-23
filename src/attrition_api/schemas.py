"""Schémas Pydantic des entrées et des sorties de l'API.

Les noms des champs sont ceux des fichiers CSV du projet 4, fautes comprises
(augementation_salaire_precedente, annes_sous_responsable_actuel).
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Note = Annotated[int, Field(ge=1, le=4)]
Annees = Annotated[int, Field(ge=0, le=50)]

# Employé 478 du jeu de test, parti de l'entreprise.
EXEMPLE_EMPLOYE = {
    "age": 21,
    "genre": "F",
    "revenu_mensuel": 2174,
    "statut_marital": "Célibataire",
    "poste": "Représentant Commercial",
    "nombre_experiences_precedentes": 1,
    "annee_experience_totale": 3,
    "annees_dans_l_entreprise": 3,
    "annees_dans_le_poste_actuel": 2,
    "satisfaction_employee_environnement": 1,
    "note_evaluation_precedente": 2,
    "satisfaction_employee_nature_travail": 2,
    "satisfaction_employee_equipe": 3,
    "satisfaction_employee_equilibre_pro_perso": 3,
    "note_evaluation_actuelle": 3,
    "heure_supplementaires": True,
    "augementation_salaire_precedente": 11,
    "nombre_participation_pee": 0,
    "nb_formations_suivies": 3,
    "distance_domicile_travail": 1,
    "niveau_education": 1,
    "domaine_etude": "Entrepreunariat",
    "frequence_deplacement": "Frequent",
    "annees_depuis_la_derniere_promotion": 1,
    "annes_sous_responsable_actuel": 2,
}

POSTES = Literal[
    "Assistant de Direction",
    "Cadre Commercial",
    "Consultant",
    "Directeur Technique",
    "Manager",
    "Représentant Commercial",
    "Ressources Humaines",
    "Senior Manager",
    "Tech Lead",
]
DOMAINES = Literal[
    "Autre",
    "Entrepreunariat",
    "Infra & Cloud",
    "Marketing",
    "Ressources Humaines",
    "Transformation Digitale",
]


class Employe(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXEMPLE_EMPLOYE]})

    age: int = Field(ge=16, le=75)
    genre: Literal["F", "M"]
    revenu_mensuel: float = Field(gt=0, le=100_000)
    statut_marital: Literal["Célibataire", "Marié(e)", "Divorcé(e)"]
    poste: POSTES
    nombre_experiences_precedentes: int = Field(ge=0, le=30)
    annee_experience_totale: Annees
    annees_dans_l_entreprise: Annees
    annees_dans_le_poste_actuel: Annees
    satisfaction_employee_environnement: Note
    note_evaluation_precedente: Note
    satisfaction_employee_nature_travail: Note
    satisfaction_employee_equipe: Note
    satisfaction_employee_equilibre_pro_perso: Note
    note_evaluation_actuelle: Note
    heure_supplementaires: bool
    augementation_salaire_precedente: float = Field(ge=0, le=100)
    nombre_participation_pee: int = Field(ge=0, le=10)
    nb_formations_suivies: int = Field(ge=0, le=20)
    distance_domicile_travail: int = Field(ge=0, le=200)
    niveau_education: int = Field(ge=1, le=5)
    domaine_etude: DOMAINES
    frequence_deplacement: Literal["Aucun", "Occasionnel", "Frequent"]
    annees_depuis_la_derniere_promotion: Annees
    annes_sous_responsable_actuel: Annees

    @model_validator(mode="after")
    def verifier_durees(self):
        # Ces règles sont vraies pour les 1 470 employés du dataset.
        erreurs = []
        if self.annee_experience_totale >= self.age:
            erreurs.append("annee_experience_totale < age")
        if self.annees_dans_l_entreprise > self.annee_experience_totale:
            erreurs.append("annees_dans_l_entreprise <= annee_experience_totale")
        anciennete = self.annees_dans_l_entreprise
        for champ in (
            "annees_dans_le_poste_actuel",
            "annes_sous_responsable_actuel",
            "annees_depuis_la_derniere_promotion",
        ):
            if getattr(self, champ) > anciennete:
                erreurs.append(f"{champ} <= annees_dans_l_entreprise")
        if erreurs:
            raise ValueError("Durées incohérentes : " + " ; ".join(erreurs))
        return self


class EmployeResume(BaseModel):
    id: int
    age: int
    genre: str
    departement: str
    poste: str


class FicheEmploye(Employe):
    """Un employé du dataset, tel que l'API le voit : sans son départ réel."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": 478, "departement": "Commercial"} | EXEMPLE_EMPLOYE]}
    )

    id: int
    departement: str


class Prediction(BaseModel):
    id_prediction: int
    id_employe: int | None = Field(None, description="Employé du dataset, s'il a été choisi")
    probabilite_depart: float = Field(ge=0, le=1)
    risque_depart: bool
    seuil: float
    version_modele: str
    calculee_le: datetime

    @classmethod
    def depuis_base(cls, ligne):
        return cls(
            id_prediction=ligne.id,
            id_employe=ligne.entree.employe_id,
            probabilite_depart=ligne.probabilite,
            risque_depart=ligne.risque_depart,
            seuil=ligne.seuil,
            version_modele=ligne.version_modele,
            calculee_le=ligne.calculee_le,
        )


class PredictionDetaillee(Prediction):
    entree: Employe


class EtatService(BaseModel):
    statut: Literal["ok"]
    version_api: str
    version_modele: str


class InfosModele(BaseModel):
    version: str
    algorithme: str
    seuil: float
    date_export: str
    variables: list[str]
    resultats_test: dict
