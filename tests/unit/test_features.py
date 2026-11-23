import pandas as pd
import pytest

from attrition_api.features import construire_features
from attrition_api.modele import charger_modele

META = charger_modele().metadonnees
MEDIANES = META["medianes_salaire_poste"]
COLONNES = META["colonnes"]


def construire(*employes):
    return construire_features(pd.DataFrame(list(employes)), MEDIANES, COLONNES)


def test_colonnes_dans_l_ordre_du_modele(exemples):
    X = construire(exemples["profil_stable"]["entree"])
    assert list(X.columns) == COLONNES
    assert len(COLONNES) == 44
    assert not X.isna().any().any()


def test_ratio_salaire_utilise_la_mediane_figee(exemples):
    employe = exemples["profil_stable"]["entree"]
    X = construire(employe)
    # Recalculée sur un seul employé, la médiane donnerait toujours un ratio de 1.
    attendu = employe["revenu_mensuel"] / MEDIANES[employe["poste"]]
    assert X.loc[0, "ratio_salaire_mediane_poste"] == pytest.approx(attendu)
    assert attendu != pytest.approx(1)


def test_un_lot_donne_le_meme_resultat_que_ligne_par_ligne(exemples):
    entrees = [e["entree"] for e in exemples.values()]
    lot = construire(*entrees)
    for i, entree in enumerate(entrees):
        pd.testing.assert_series_equal(lot.iloc[i], construire(entree).iloc[0], check_names=False)


def test_premier_emploi_sans_division_par_zero(exemples):
    X = construire(exemples["premier_emploi"]["entree"])
    assert X.loc[0, "part_carriere_technova"] == 1.0
    assert X.loc[0, "annees_par_employeur"] == 0.0


def test_encodage_des_variables_qualitatives(exemples):
    X = construire(exemples["profil_a_risque"]["entree"])
    ligne = X.loc[0]
    assert ligne["genre"] == 1
    assert ligne["heure_supplementaires"] == 1
    assert ligne["frequence_deplacement"] == 2
    assert ligne["poste_Représentant Commercial"] == 1
    assert ligne.filter(regex="^poste_").sum() == 1
    assert ligne.filter(regex="^statut_marital_").sum() == 1
    assert ligne.filter(regex="^domaine_etude_").sum() == 1


def test_satisfaction_moyenne(exemples):
    employe = exemples["profil_stable"]["entree"]
    X = construire(employe)
    notes = [v for k, v in employe.items() if k.startswith("satisfaction_employee_")]
    assert X.loc[0, "satisfaction_moyenne"] == pytest.approx(sum(notes) / 4)
