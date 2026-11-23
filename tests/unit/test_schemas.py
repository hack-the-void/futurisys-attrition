import pytest
from pydantic import ValidationError

from attrition_api.schemas import EXEMPLE_EMPLOYE, Employe


def test_exemple_de_la_documentation_valide():
    assert Employe(**EXEMPLE_EMPLOYE).model_dump() == EXEMPLE_EMPLOYE


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("age", 15),
        ("genre", "X"),
        ("revenu_mensuel", 0),
        ("poste", "Stagiaire"),
        ("satisfaction_employee_equipe", 5),
        ("note_evaluation_actuelle", 0),
        ("frequence_deplacement", "Rare"),
        ("augementation_salaire_precedente", -1),
    ],
)
def test_valeur_hors_domaine_refusee(champ, valeur):
    with pytest.raises(ValidationError, match=champ):
        Employe(**EXEMPLE_EMPLOYE | {champ: valeur})


def test_champ_manquant_refuse():
    entree = {k: v for k, v in EXEMPLE_EMPLOYE.items() if k != "poste"}
    with pytest.raises(ValidationError, match="poste"):
        Employe(**entree)


def test_champ_inconnu_refuse():
    # Un champ en trop signale souvent une faute de frappe côté client.
    with pytest.raises(ValidationError, match="departement"):
        Employe(**EXEMPLE_EMPLOYE | {"departement": "Commercial"})


@pytest.mark.parametrize(
    ("modifications", "regle"),
    [
        ({"age": 20, "annee_experience_totale": 20}, "annee_experience_totale < age"),
        ({"annees_dans_l_entreprise": 6}, "annees_dans_l_entreprise <= annee_experience_totale"),
        ({"annees_dans_le_poste_actuel": 4}, "annees_dans_le_poste_actuel <= annees_dans_l"),
        ({"annes_sous_responsable_actuel": 4}, "annes_sous_responsable_actuel <= annees_dans_l"),
        ({"annees_depuis_la_derniere_promotion": 4}, "annees_depuis_la_derniere_promotion <="),
    ],
)
def test_durees_incoherentes_refusees(modifications, regle):
    with pytest.raises(ValidationError, match="Durées incohérentes") as erreur:
        Employe(**EXEMPLE_EMPLOYE | modifications)
    assert regle in str(erreur.value)
