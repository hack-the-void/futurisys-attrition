# Base de données

La base contient le dataset complet du projet 4 (1 470 employés) et toutes les prédictions
du modèle : celles calculées sur le dataset à l'import, et celles demandées à l'API. On garde
ainsi la trace de ce que le modèle a dit, sur quelles données et avec quelle version, et on
peut comparer ses alertes aux départs réels.

## Schéma

```mermaid
erDiagram
    employes |o--o{ entrees : "est envoyé en"
    modeles ||--o{ predictions : "calcule"
    entrees ||--o{ predictions : "reçoit"

    employes {
        int id PK "id_employee des extraits RH"
        varchar jeu "train ou test"
        bool a_quitte_l_entreprise "la cible"
        varchar departement
        int autres_champs "les 31 colonnes du dataset"
    }

    modeles {
        varchar version PK "ex. 1.0.0"
        varchar algorithme
        float seuil
        timestamptz date_export
        varchar sha256 "empreinte du fichier joblib"
        json resultats_test "précision, rappel, PR-AUC..."
        timestamptz enregistre_le
    }
    entrees {
        serial id PK
        timestamptz recue_le
        varchar source "api, script ou dataset"
        int employe_id FK "rempli pour le dataset"
        int age
        varchar poste
        float revenu_mensuel
        bool heure_supplementaires
        int autres_champs "21 autres champs RH"
    }
    predictions {
        serial id PK
        int entree_id FK
        varchar version_modele FK
        float probabilite "entre 0 et 1"
        float seuil
        bool risque_depart
        timestamptz calculee_le
    }
```

Le script SQL complet est dans [db/schema.sql](../db/schema.sql). Il est généré à partir de
[src/attrition_api/db.py](../src/attrition_api/db.py), et un test vérifie que les deux
restent identiques.

## Les tables

| Table | Une ligne par | Rôle |
| --- | --- | --- |
| `employes` | employé du dataset | Les trois extraits RH fusionnés, avec la cible et le jeu (`train` ou `test`) du projet 4. |
| `modeles` | version de modèle servie | Ajoutée au démarrage de l'API. Garde le seuil, l'empreinte et les résultats du test. |
| `entrees` | employé envoyé au modèle | Les 25 champs RH validés, avec la date et l'origine de l'envoi. Lien vers `employes` pour le dataset. |
| `predictions` | calcul d'un modèle sur une entrée | Probabilité, seuil appliqué et alerte. |

## Choix de conception

- **Dataset brut à part.** `employes` garde toutes les colonnes des extraits, y compris
  celles que le modèle ignore (département, heures de travail...). `entrees` ne contient
  que ce que le modèle reçoit, quelle que soit l'origine. Les prédictions du dataset et de
  l'API se lisent donc avec les mêmes requêtes.
- **Entrées et prédictions séparées.** Une entrée peut recevoir une prédiction par version
  de modèle (contrainte `UNIQUE (entree_id, version_modele)`). Après un nouvel entraînement,
  on peut recalculer l'historique et comparer les deux modèles sur les mêmes employés.
- **Une colonne par champ RH plutôt qu'un JSON.** Les requêtes restent simples
  (`GROUP BY poste`) et PostgreSQL vérifie les types. Les colonnes reprennent les noms du
  schéma de l'API, et un test le vérifie.
- **Seuil copié dans chaque prédiction.** Le seuil d'un modèle ne change pas, mais la ligne
  reste lisible seule, et `risque_depart` peut être vérifié sans jointure.
- **Contrôles dans la base.** La probabilité doit être comprise entre 0 et 1. Les clés
  étrangères empêchent une prédiction sans entrée ou sans modèle connu.
- **Même version, même fichier.** Au démarrage, l'API refuse une version déjà enregistrée
  avec une autre empreinte : un modèle ré-exporté doit changer de version.
- **Une transaction par appel.** L'entrée et sa prédiction sont écrites ensemble. Un appel
  refusé (clé invalide, données invalides) n'écrit rien.
- **Index.** Ils portent sur les colonnes filtrées dans les requêtes d'exemple : date de
  réception, poste, alerte et version.

## Accès

Deux comptes PostgreSQL, chacun avec son mot de passe dans `.env` :

| Compte | Variable | Droits | Utilisé par |
| --- | --- | --- | --- |
| `attrition` | `ADMIN_DATABASE_URL` | Propriétaire de la base | `create_db`, l'import du dataset, `interroger_db.py` |
| `api_attrition` | `DATABASE_URL` | `SELECT` et `INSERT` sur `modeles`, `entrees` et `predictions` | L'API |

L'API ne peut donc ni modifier ni supprimer une prédiction, ni lire la table `employes`
(qui contient la cible), ni créer ou supprimer une table. Si elle était compromise, elle
ne pourrait pas effacer l'historique. `PUBLIC` perd aussi ses droits par défaut sur la
base. Les instructions `GRANT` sont dans [src/attrition_api/acces.py](../src/attrition_api/acces.py)
et à la fin de [db/schema.sql](../db/schema.sql). Des tests se connectent avec ce rôle
et vérifient chaque refus.

## Créer la base et importer le dataset

```bash
docker compose up -d db
uv run python -m attrition_api.create_db --roles      # tables, rôle de l'API et droits
uv run python scripts/importer_dataset.py --source ../technova-attrition
```

`create_db` utilise le compte propriétaire. `--roles` crée `api_attrition` avec le mot de
passe `API_DB_PASSWORD`, ou le met à jour. `--reinitialiser` supprime puis recrée les
tables. `--sql` affiche le script SQL sans l'exécuter. Avec `docker compose up`, le service
`init-db` lance `create_db --roles` avant l'API.

L'import lit les trois CSV du projet 4 et prend la liste du jeu de test dans son artefact
(`artefacts/modele_final.joblib`), qui restent hors de Git. Il insère les 1 470 employés,
puis enregistre une prédiction du modèle pour chacun (source `dataset`). On peut le
relancer : il remplace les données du dataset sans toucher aux appels de l'API.
`--sans-predictions` n'insère que les employés.

```text
$ uv run python scripts/interroger_db.py performances_test
version_modele  employes  departs  vrais_positifs  fausses_alertes  departs_manques  rappel
         1.0.0       294       47              33               64               14   0.702
```

Recalculés depuis la base, les résultats sur le jeu de test sont ceux du projet 4.

## Requêtes

[db/requetes.sql](../db/requetes.sql) contient des requêtes nommées : synthèse, alertes par
poste, performances sur le test, départs par département... Elles portent sur le dataset
importé et sur les appels reçus par l'API.

```bash
uv run python scripts/interroger_db.py --liste
uv run python scripts/interroger_db.py alertes_par_poste
uv run python scripts/interroger_db.py departs_par_departement
uv run python scripts/interroger_db.py export --csv predictions.csv
```

## Données personnelles

Les tables `employes` et `entrees` contiennent des données RH personnelles, dont le genre
et le statut marital. La base ne tourne qu'en local, sur `127.0.0.1`, et l'API n'a pas
accès à `employes`. En production, il faudrait aussi fixer une durée de conservation et
pouvoir supprimer un employé. La suppression d'une entrée supprime ses prédictions
(`ON DELETE CASCADE`). Le dataset n'est pas versionné. Seuls trois employés du jeu de test
(478, 734 et 1839) sont dans le dépôt : ils servent d'exemple dans Swagger et de références
dans les tests.
