"""Modèle de données PostgreSQL et accès aux prédictions enregistrées.

Quatre tables :
- `employes` : le dataset du projet 4, 1 470 employés avec leur départ réel ;
- `modeles` : une ligne par version de modèle servie par l'API ;
- `entrees` : les 25 champs RH envoyés au modèle, tels que validés par l'API ;
- `predictions` : le résultat d'un modèle pour une entrée.

Une entrée peut recevoir plusieurs prédictions, une par version de modèle. On peut ainsi
recalculer l'historique avec un nouveau modèle et comparer les deux sur les mêmes données.
Quand l'utilisateur choisit un employé du dataset, l'entrée pointe vers lui : on peut
alors comparer la prédiction au départ réel directement en SQL.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    RowMapping,
    String,
    UniqueConstraint,
    create_engine,
    func,
    inspect,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from attrition_api.modele import ModeleAttrition


class Base(DeclarativeBase):
    pass


class EmployeDataset(Base):
    """Une ligne des trois extraits RH rapprochés, nettoyés mais complets."""

    __tablename__ = "employes"
    __table_args__ = (CheckConstraint("jeu IN ('train', 'test')", name="jeu_train_ou_test"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, comment="id_employee")
    jeu: Mapped[str] = mapped_column(String(5), index=True, comment="Découpage du projet 4")
    a_quitte_l_entreprise: Mapped[bool] = mapped_column(comment="Départ réel, la cible")

    # SIRH
    age: Mapped[int]
    genre: Mapped[str] = mapped_column(String(1))
    revenu_mensuel: Mapped[float]
    statut_marital: Mapped[str] = mapped_column(String(20))
    departement: Mapped[str] = mapped_column(String(50))
    poste: Mapped[str] = mapped_column(String(50))
    nombre_experiences_precedentes: Mapped[int]
    nombre_heures_travailless: Mapped[int]
    annee_experience_totale: Mapped[int]
    annees_dans_l_entreprise: Mapped[int]
    annees_dans_le_poste_actuel: Mapped[int]
    # Évaluations
    satisfaction_employee_environnement: Mapped[int]
    note_evaluation_precedente: Mapped[int]
    niveau_hierarchique_poste: Mapped[int]
    satisfaction_employee_nature_travail: Mapped[int]
    satisfaction_employee_equipe: Mapped[int]
    satisfaction_employee_equilibre_pro_perso: Mapped[int]
    note_evaluation_actuelle: Mapped[int]
    heure_supplementaires: Mapped[bool]
    augementation_salaire_precedente: Mapped[float]
    # Sondage
    nombre_participation_pee: Mapped[int]
    nb_formations_suivies: Mapped[int]
    nombre_employee_sous_responsabilite: Mapped[int]
    distance_domicile_travail: Mapped[int]
    niveau_education: Mapped[int]
    domaine_etude: Mapped[str] = mapped_column(String(50))
    ayant_enfants: Mapped[str] = mapped_column(String(1))
    frequence_deplacement: Mapped[str] = mapped_column(String(20))
    annees_depuis_la_derniere_promotion: Mapped[int]
    annes_sous_responsable_actuel: Mapped[int]


class ModeleEnregistre(Base):
    __tablename__ = "modeles"

    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    algorithme: Mapped[str] = mapped_column(String(100))
    seuil: Mapped[float] = mapped_column(Float)
    date_export: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(String(64))
    resultats_test: Mapped[dict[str, Any]] = mapped_column(JSON)
    enregistre_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Entree(Base):
    __tablename__ = "entrees"

    id: Mapped[int] = mapped_column(primary_key=True)
    recue_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    source: Mapped[str] = mapped_column(String(20), comment="api, ou le nom d'un script")
    employe_id: Mapped[int | None] = mapped_column(
        ForeignKey("employes.id"), index=True, comment="Employé du dataset choisi, s'il y en a un"
    )

    # Les 25 champs de attrition_api.schemas.Employe.
    age: Mapped[int]
    genre: Mapped[str] = mapped_column(String(1))
    revenu_mensuel: Mapped[float]
    statut_marital: Mapped[str] = mapped_column(String(20))
    poste: Mapped[str] = mapped_column(String(50), index=True)
    nombre_experiences_precedentes: Mapped[int]
    annee_experience_totale: Mapped[int]
    annees_dans_l_entreprise: Mapped[int]
    annees_dans_le_poste_actuel: Mapped[int]
    satisfaction_employee_environnement: Mapped[int]
    note_evaluation_precedente: Mapped[int]
    satisfaction_employee_nature_travail: Mapped[int]
    satisfaction_employee_equipe: Mapped[int]
    satisfaction_employee_equilibre_pro_perso: Mapped[int]
    note_evaluation_actuelle: Mapped[int]
    heure_supplementaires: Mapped[bool]
    augementation_salaire_precedente: Mapped[float]
    nombre_participation_pee: Mapped[int]
    nb_formations_suivies: Mapped[int]
    distance_domicile_travail: Mapped[int]
    niveau_education: Mapped[int]
    domaine_etude: Mapped[str] = mapped_column(String(50))
    frequence_deplacement: Mapped[str] = mapped_column(String(20))
    annees_depuis_la_derniere_promotion: Mapped[int]
    annes_sous_responsable_actuel: Mapped[int]

    predictions: Mapped[list["PredictionEnregistree"]] = relationship(back_populates="entree")


class PredictionEnregistree(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("entree_id", "version_modele"),
        CheckConstraint("probabilite BETWEEN 0 AND 1", name="probabilite_entre_0_et_1"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entree_id: Mapped[int] = mapped_column(ForeignKey("entrees.id", ondelete="CASCADE"))
    version_modele: Mapped[str] = mapped_column(ForeignKey("modeles.version"), index=True)
    probabilite: Mapped[float]
    seuil: Mapped[float] = mapped_column(comment="Seuil du modèle au moment de la prédiction")
    risque_depart: Mapped[bool] = mapped_column(index=True)
    calculee_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    entree: Mapped[Entree] = relationship(back_populates="predictions")


TABLES = [
    EmployeDataset.__table__,
    ModeleEnregistre.__table__,
    Entree.__table__,
    PredictionEnregistree.__table__,
]
CHAMPS_ENTREE = [
    c.name
    for c in Entree.__table__.columns
    if c.name not in {"id", "recue_le", "source", "employe_id"}
]
# Colonnes de `employes` que l'API peut lire : ni la cible, ni le découpage train/test,
# ni les colonnes que le modèle n'utilise pas.
COLONNES_EMPLOYE_API = ["id", "departement", *CHAMPS_ENTREE]


def creer_moteur(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def tables_manquantes(moteur: Engine) -> list[str]:
    existantes = set(inspect(moteur).get_table_names())
    return [t.name for t in TABLES if t.name not in existantes]


def enregistrer_modele(session: Session, modele: ModeleAttrition) -> None:
    """Ajoute la version du modèle si elle n'est pas encore en base."""
    meta = modele.metadonnees
    existant = session.get(ModeleEnregistre, modele.version)
    if existant is not None:
        # Deux fichiers différents sous la même version rendraient l'historique ambigu.
        if existant.sha256 != meta["sha256_modele"]:
            raise RuntimeError(
                f"La version {modele.version} est déjà enregistrée avec un autre fichier : "
                "changer VERSION_MODELE dans scripts/exporter_modele.py"
            )
        return
    session.add(
        ModeleEnregistre(
            version=modele.version,
            algorithme=meta["algorithme"],
            seuil=modele.seuil,
            date_export=datetime.fromisoformat(meta["date_export"]),
            sha256=meta["sha256_modele"],
            resultats_test=meta["resultats_test"],
        )
    )
    session.commit()


def enregistrer_prediction(
    session: Session,
    employe: Mapping[str, Any],
    probabilite: float,
    modele: ModeleAttrition,
    source: str,
    employe_id: int | None = None,
    valider: bool = True,
) -> PredictionEnregistree:
    """Enregistre l'entrée et sa prédiction dans la même transaction.

    Avec `valider=False`, la transaction reste ouverte pour regrouper plusieurs écritures.
    """
    prediction = PredictionEnregistree(
        entree=Entree(source=source, employe_id=employe_id, **employe),
        version_modele=modele.version,
        probabilite=probabilite,
        seuil=modele.seuil,
        risque_depart=probabilite >= modele.seuil,
    )
    session.add(prediction)
    if valider:
        session.commit()
    return prediction


def lister_predictions(session: Session, limite: int) -> list[PredictionEnregistree]:
    requete = select(PredictionEnregistree).order_by(PredictionEnregistree.id.desc()).limit(limite)
    return list(session.scalars(requete))


def lister_employes(
    session: Session,
    limite: int,
    decalage: int = 0,
    departement: str | None = None,
    poste: str | None = None,
) -> list[RowMapping]:
    t = EmployeDataset.__table__.c
    requete = select(t.id, t.age, t.genre, t.departement, t.poste)
    if departement:
        requete = requete.where(t.departement == departement)
    if poste:
        requete = requete.where(t.poste == poste)
    requete = requete.order_by(t.id).offset(decalage).limit(limite)
    return list(session.execute(requete).mappings())


def lire_employe(session: Session, id_employe: int) -> RowMapping | None:
    """Les colonnes d'un employé que l'API a le droit de lire."""
    colonnes = [EmployeDataset.__table__.c[nom] for nom in COLONNES_EMPLOYE_API]
    requete = select(*colonnes).where(EmployeDataset.id == id_employe)
    return session.execute(requete).mappings().one_or_none()
