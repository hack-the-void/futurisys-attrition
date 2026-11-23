-- Requêtes d'exemple sur le dataset et les prédictions enregistrées.
-- Chaque bloc commence par « -- nom: ». Pour en exécuter une :
--   uv run python scripts/interroger_db.py synthese
-- Ou dans psql :
--   docker compose exec db psql -U attrition -d attrition

-- nom: dernieres
-- Les dix dernières prédictions.
SELECT p.id, p.calculee_le, e.source, e.poste, e.age, p.probabilite, p.risque_depart,
       p.version_modele
FROM predictions p
JOIN entrees e ON e.id = p.entree_id
ORDER BY p.id DESC
LIMIT 10;

-- nom: synthese
-- Volume, alertes et probabilité moyenne par version du modèle et par origine.
SELECT p.version_modele, e.source, m.seuil, COUNT(*) AS predictions,
       SUM(CASE WHEN p.risque_depart THEN 1 ELSE 0 END) AS alertes,
       AVG(p.probabilite) AS probabilite_moyenne
FROM predictions p
JOIN modeles m ON m.version = p.version_modele
JOIN entrees e ON e.id = p.entree_id
GROUP BY p.version_modele, e.source, m.seuil
ORDER BY p.version_modele, e.source;

-- nom: alertes_par_poste
-- Taux d'alerte par poste, du plus élevé au plus faible.
SELECT e.poste, COUNT(*) AS predictions,
       SUM(CASE WHEN p.risque_depart THEN 1 ELSE 0 END) AS alertes,
       AVG(CASE WHEN p.risque_depart THEN 1.0 ELSE 0.0 END) AS taux_alerte
FROM predictions p
JOIN entrees e ON e.id = p.entree_id
GROUP BY e.poste
ORDER BY taux_alerte DESC, e.poste;

-- nom: heures_supplementaires
-- Probabilité moyenne selon les heures supplémentaires, premier facteur du modèle.
SELECT e.heure_supplementaires, COUNT(*) AS predictions,
       AVG(p.probabilite) AS probabilite_moyenne
FROM predictions p
JOIN entrees e ON e.id = p.entree_id
GROUP BY e.heure_supplementaires
ORDER BY e.heure_supplementaires;

-- nom: profils_a_risque
-- Les dix alertes les plus fortes, avec quelques champs pour préparer un entretien.
SELECT p.id, e.poste, e.age, e.revenu_mensuel, e.heure_supplementaires,
       e.satisfaction_employee_environnement, e.satisfaction_employee_equilibre_pro_perso,
       e.annees_dans_l_entreprise, p.probabilite
FROM predictions p
JOIN entrees e ON e.id = p.entree_id
WHERE p.risque_depart
ORDER BY p.probabilite DESC
LIMIT 10;

-- nom: performances_test
-- Résultats du modèle sur le jeu de test du projet 4, recalculés depuis la base :
-- prédictions enregistrées comparées aux départs réels de la table employes.
SELECT p.version_modele, COUNT(*) AS employes,
       SUM(CASE WHEN emp.a_quitte_l_entreprise THEN 1 ELSE 0 END) AS departs,
       SUM(CASE WHEN p.risque_depart AND emp.a_quitte_l_entreprise THEN 1 ELSE 0 END) AS vrais_positifs,
       SUM(CASE WHEN p.risque_depart AND NOT emp.a_quitte_l_entreprise THEN 1 ELSE 0 END) AS fausses_alertes,
       SUM(CASE WHEN NOT p.risque_depart AND emp.a_quitte_l_entreprise THEN 1 ELSE 0 END) AS departs_manques,
       AVG(CASE WHEN emp.a_quitte_l_entreprise
                THEN CASE WHEN p.risque_depart THEN 1.0 ELSE 0.0 END END) AS rappel
FROM predictions p
JOIN entrees e ON e.id = p.entree_id
JOIN employes emp ON emp.id = e.employe_id
WHERE emp.jeu = 'test'
GROUP BY p.version_modele
ORDER BY p.version_modele;

-- nom: departs_par_departement
-- Taux de départ réel et taux d'alerte par département, sur tout le dataset.
SELECT emp.departement, COUNT(*) AS employes,
       AVG(CASE WHEN emp.a_quitte_l_entreprise THEN 1.0 ELSE 0.0 END) AS taux_depart_reel,
       AVG(CASE WHEN p.risque_depart THEN 1.0 ELSE 0.0 END) AS taux_alerte
FROM employes emp
JOIN entrees e ON e.employe_id = emp.id
JOIN predictions p ON p.entree_id = e.id
GROUP BY emp.departement
ORDER BY taux_depart_reel DESC;

-- nom: export
-- Toutes les entrées avec leur prédiction, pour un export CSV.
SELECT e.*, p.id AS id_prediction, p.version_modele, p.probabilite, p.seuil,
       p.risque_depart, p.calculee_le
FROM entrees e
JOIN predictions p ON p.entree_id = e.id
ORDER BY p.id;
