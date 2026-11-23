"""Génère des employés fictifs pour alimenter la base de démonstration.

Les profils sont tirés au hasard avec une graine fixe, dans les bornes et les règles de
cohérence de l'API. Ils ne proviennent pas des données RH.

Usage :
    uv run python scripts/generer_employes_fictifs.py --nombre 50
"""

import argparse
import csv
import random
from pathlib import Path
from typing import get_args

from attrition_api.modele import charger_modele
from attrition_api.schemas import Employe

RACINE = Path(__file__).resolve().parents[1]
FICHIER_SORTIE = RACINE / "db" / "exemples" / "employes_fictifs.csv"


def choix(champ: str) -> tuple:
    return get_args(Employe.model_fields[champ].annotation)


def generer(alea: random.Random, medianes: dict[str, float]) -> dict:
    age = alea.randint(20, 60)
    experience = alea.randint(0, min(40, age - 18))
    anciennete = alea.randint(0, experience)
    poste = alea.choice(choix("poste"))
    return {
        "age": age,
        "genre": alea.choice(choix("genre")),
        "revenu_mensuel": round(medianes[poste] * alea.uniform(0.6, 1.4)),
        "statut_marital": alea.choice(choix("statut_marital")),
        "poste": poste,
        "nombre_experiences_precedentes": alea.randint(0, 9),
        "annee_experience_totale": experience,
        "annees_dans_l_entreprise": anciennete,
        "annees_dans_le_poste_actuel": alea.randint(0, anciennete),
        "satisfaction_employee_environnement": alea.randint(1, 4),
        "note_evaluation_precedente": alea.randint(1, 4),
        "satisfaction_employee_nature_travail": alea.randint(1, 4),
        "satisfaction_employee_equipe": alea.randint(1, 4),
        "satisfaction_employee_equilibre_pro_perso": alea.randint(1, 4),
        "note_evaluation_actuelle": alea.randint(3, 4),
        "heure_supplementaires": alea.random() < 0.3,
        "augementation_salaire_precedente": alea.randint(11, 25),
        "nombre_participation_pee": alea.randint(0, 3),
        "nb_formations_suivies": alea.randint(0, 6),
        "distance_domicile_travail": alea.randint(1, 29),
        "niveau_education": alea.randint(1, 5),
        "domaine_etude": alea.choice(choix("domaine_etude")),
        "frequence_deplacement": alea.choices(choix("frequence_deplacement"), [2, 7, 1])[0],
        "annees_depuis_la_derniere_promotion": alea.randint(0, anciennete),
        "annes_sous_responsable_actuel": alea.randint(0, anciennete),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des employés fictifs.")
    parser.add_argument("--nombre", type=int, default=50)
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()

    alea = random.Random(args.graine)
    medianes = charger_modele().metadonnees["medianes_salaire_poste"]
    # La validation garantit que chaque profil serait accepté par l'API.
    employes = [Employe(**generer(alea, medianes)).model_dump() for _ in range(args.nombre)]

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=list(Employe.model_fields))
        ecrivain.writeheader()
        ecrivain.writerows(employes)
    print(f"{len(employes)} employés écrits dans {FICHIER_SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
