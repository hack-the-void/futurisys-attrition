"""Schémas d'entrée et de sortie de l'API.

Les noms des champs reprennent ceux des extraits RH, fautes de frappe comprises
(`augementation_salaire_precedente`, `annes_sous_responsable_actuel`), pour rester
traçables jusqu'aux données d'entraînement.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Note = Annotated[int, Field(ge=1, le=4)]
Annees = Annotated[int, Field(ge=0, le=50)]

EXEMPLE_EMPLOYE = {
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
}


class Employe(BaseModel):
    """Les 25 champs RH utilisés par le modèle, pour un employé."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXEMPLE_EMPLOYE]})

    # SIRH
    age: int = Field(ge=16, le=75)
    genre: Literal["F", "M"]
    revenu_mensuel: float = Field(gt=0, le=100_000, description="Salaire mensuel brut")
    statut_marital: Literal["Célibataire", "Marié(e)", "Divorcé(e)"]
    poste: Literal[
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
    nombre_experiences_precedentes: int = Field(ge=0, le=30)
    annee_experience_totale: Annees
    annees_dans_l_entreprise: Annees
    annees_dans_le_poste_actuel: Annees

    # Évaluations
    satisfaction_employee_environnement: Note
    note_evaluation_precedente: Note
    satisfaction_employee_nature_travail: Note
    satisfaction_employee_equipe: Note
    satisfaction_employee_equilibre_pro_perso: Note
    note_evaluation_actuelle: Note
    heure_supplementaires: bool
    augementation_salaire_precedente: float = Field(
        ge=0, le=100, description="Dernière augmentation, en pourcentage"
    )

    # Sondage
    nombre_participation_pee: int = Field(ge=0, le=10)
    nb_formations_suivies: int = Field(ge=0, le=20)
    distance_domicile_travail: int = Field(ge=0, le=200, description="En kilomètres")
    niveau_education: int = Field(ge=1, le=5)
    domaine_etude: Literal[
        "Autre",
        "Entrepreunariat",
        "Infra & Cloud",
        "Marketing",
        "Ressources Humaines",
        "Transformation Digitale",
    ]
    frequence_deplacement: Literal["Aucun", "Occasionnel", "Frequent"]
    annees_depuis_la_derniere_promotion: Annees
    annes_sous_responsable_actuel: Annees

    @model_validator(mode="after")
    def _verifier_les_durees(self) -> Self:
        # Règles vérifiées sur les 1 470 employés des données d'entraînement.
        regles = [
            (self.annee_experience_totale < self.age, "annee_experience_totale < age"),
            (
                self.annees_dans_l_entreprise <= self.annee_experience_totale,
                "annees_dans_l_entreprise <= annee_experience_totale",
            ),
            (
                self.annees_dans_le_poste_actuel <= self.annees_dans_l_entreprise,
                "annees_dans_le_poste_actuel <= annees_dans_l_entreprise",
            ),
            (
                self.annes_sous_responsable_actuel <= self.annees_dans_l_entreprise,
                "annes_sous_responsable_actuel <= annees_dans_l_entreprise",
            ),
            (
                self.annees_depuis_la_derniere_promotion <= self.annees_dans_l_entreprise,
                "annees_depuis_la_derniere_promotion <= annees_dans_l_entreprise",
            ),
        ]
        violees = [texte for respectee, texte in regles if not respectee]
        if violees:
            raise ValueError("Durées incohérentes : " + " ; ".join(violees))
        return self


class Prediction(BaseModel):
    id_prediction: int = Field(description="Identifiant de la prédiction en base")
    probabilite_depart: float = Field(ge=0, le=1, description="Probabilité estimée de départ")
    risque_depart: bool = Field(description="Vrai si la probabilité atteint le seuil")
    seuil: float = Field(description="Seuil d'alerte du modèle")
    version_modele: str
    calculee_le: datetime

    @classmethod
    def depuis_base(cls, ligne: Any) -> Self:
        return cls(
            id_prediction=ligne.id,
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
