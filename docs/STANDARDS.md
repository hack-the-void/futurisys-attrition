# Conventions du projet

## Git et Python

- Ouvrir une PR vers `main` depuis une branche courte comme `feature/endpoint-prediction`.
  Les préfixes utilisés ici sont `feature`, `fix`, `test`, `docs`, `ci` et `chore`.
- Écrire les messages au format `type: description`, par exemple
  `feat: ajoute l'endpoint de prédiction`. Fusionner les PR avec un commit de merge.
- En cas de conflit, récupérer `origin/main`, le fusionner dans la branche de travail,
  résoudre les conflits et relancer les tests avant de pousser sans force.
- Garder la version du paquet et le tag `vX.Y.Z` cohérents. Le projet reste en `0.x`
  pendant le POC. Voir [la procédure de livraison](CI_CD.md#publier-une-version).
- Utiliser Python 3.12, Ruff et pytest. Garder au moins 80 % de couverture. Les tests
  doivent passer avec ou sans un fichier `.env` local.

## Entraînement et évaluation

Fixer la graine à 42 et faire un découpage stratifié 80/20. Sur le train, comparer
les modèles par validation croisée stratifiée à cinq plis et choisir les hyperparamètres
sur la PR-AUC. Choisir le seuil sur les prédictions hors pli en maximisant le F2 pour
donner plus de poids aux départs manqués. Réserver le test à la mesure finale.

Consigner la précision, le rappel, F1, F2, la PR-AUC et la matrice de confusion sur le test.
Pour remplacer le modèle, comparer les deux sur le même jeu de test et vérifier que la
PR-AUC progresse sans baisse de rappel au seuil retenu.

### Paramètres appris

Calculer les paramètres sur le train et les figer avec le modèle. Par exemple,
`ratio_salaire_mediane_poste` utilise une médiane par poste apprise à l'entraînement.
Recalculée sur un seul employé, cette médiane serait son salaire et le ratio vaudrait 1.

Dans le projet 4, les médianes ont été calculées sur l'ensemble des données, test compris.
Pour reproduire les prédictions du modèle actuel, garder ces valeurs jusqu'au prochain
entraînement. Au prochain entraînement, les recalculer sur le train.

### Artefact de modèle

Le fichier du projet 4 contient aussi les jeux d'entraînement et de test. Le garder hors
du dépôt et le recharger avec scikit-learn 1.9.1 sous Python 3.12.

Pour la livraison, exporter le modèle, son seuil et les paramètres figés sans les données
RH. Joindre la date, les versions des données et des bibliothèques, le commit d'entraînement,
les hyperparamètres et les résultats du test.
