-- Généré par : uv run python -m attrition_api.create_db --sql db/schema.sql

CREATE TABLE employes (
	id INTEGER NOT NULL, 
	jeu VARCHAR(5) NOT NULL, 
	a_quitte_l_entreprise BOOLEAN NOT NULL, 
	age INTEGER NOT NULL, 
	genre VARCHAR(1) NOT NULL, 
	revenu_mensuel DOUBLE PRECISION NOT NULL, 
	statut_marital VARCHAR(20) NOT NULL, 
	departement VARCHAR(50) NOT NULL, 
	poste VARCHAR(50) NOT NULL, 
	nombre_experiences_precedentes INTEGER NOT NULL, 
	nombre_heures_travailless INTEGER NOT NULL, 
	annee_experience_totale INTEGER NOT NULL, 
	annees_dans_l_entreprise INTEGER NOT NULL, 
	annees_dans_le_poste_actuel INTEGER NOT NULL, 
	satisfaction_employee_environnement INTEGER NOT NULL, 
	note_evaluation_precedente INTEGER NOT NULL, 
	niveau_hierarchique_poste INTEGER NOT NULL, 
	satisfaction_employee_nature_travail INTEGER NOT NULL, 
	satisfaction_employee_equipe INTEGER NOT NULL, 
	satisfaction_employee_equilibre_pro_perso INTEGER NOT NULL, 
	note_evaluation_actuelle INTEGER NOT NULL, 
	heure_supplementaires BOOLEAN NOT NULL, 
	augementation_salaire_precedente DOUBLE PRECISION NOT NULL, 
	nombre_participation_pee INTEGER NOT NULL, 
	nb_formations_suivies INTEGER NOT NULL, 
	nombre_employee_sous_responsabilite INTEGER NOT NULL, 
	distance_domicile_travail INTEGER NOT NULL, 
	niveau_education INTEGER NOT NULL, 
	domaine_etude VARCHAR(50) NOT NULL, 
	ayant_enfants VARCHAR(1) NOT NULL, 
	frequence_deplacement VARCHAR(20) NOT NULL, 
	annees_depuis_la_derniere_promotion INTEGER NOT NULL, 
	annes_sous_responsable_actuel INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT jeu_train_ou_test CHECK (jeu IN ('train', 'test'))
);

CREATE INDEX ix_employes_jeu ON employes (jeu);

CREATE TABLE modeles (
	version VARCHAR(20) NOT NULL, 
	algorithme VARCHAR(100) NOT NULL, 
	seuil FLOAT NOT NULL, 
	date_export TIMESTAMP WITH TIME ZONE NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	resultats_test JSON NOT NULL, 
	enregistre_le TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (version)
);

CREATE TABLE entrees (
	id SERIAL NOT NULL, 
	recue_le TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	employe_id INTEGER, 
	age INTEGER NOT NULL, 
	genre VARCHAR(1) NOT NULL, 
	revenu_mensuel DOUBLE PRECISION NOT NULL, 
	statut_marital VARCHAR(20) NOT NULL, 
	poste VARCHAR(50) NOT NULL, 
	nombre_experiences_precedentes INTEGER NOT NULL, 
	annee_experience_totale INTEGER NOT NULL, 
	annees_dans_l_entreprise INTEGER NOT NULL, 
	annees_dans_le_poste_actuel INTEGER NOT NULL, 
	satisfaction_employee_environnement INTEGER NOT NULL, 
	note_evaluation_precedente INTEGER NOT NULL, 
	satisfaction_employee_nature_travail INTEGER NOT NULL, 
	satisfaction_employee_equipe INTEGER NOT NULL, 
	satisfaction_employee_equilibre_pro_perso INTEGER NOT NULL, 
	note_evaluation_actuelle INTEGER NOT NULL, 
	heure_supplementaires BOOLEAN NOT NULL, 
	augementation_salaire_precedente DOUBLE PRECISION NOT NULL, 
	nombre_participation_pee INTEGER NOT NULL, 
	nb_formations_suivies INTEGER NOT NULL, 
	distance_domicile_travail INTEGER NOT NULL, 
	niveau_education INTEGER NOT NULL, 
	domaine_etude VARCHAR(50) NOT NULL, 
	frequence_deplacement VARCHAR(20) NOT NULL, 
	annees_depuis_la_derniere_promotion INTEGER NOT NULL, 
	annes_sous_responsable_actuel INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employe_id) REFERENCES employes (id)
);

CREATE INDEX ix_entrees_employe_id ON entrees (employe_id);

CREATE INDEX ix_entrees_poste ON entrees (poste);

CREATE INDEX ix_entrees_recue_le ON entrees (recue_le);

CREATE TABLE predictions (
	id SERIAL NOT NULL, 
	entree_id INTEGER NOT NULL, 
	version_modele VARCHAR(20) NOT NULL, 
	probabilite DOUBLE PRECISION NOT NULL, 
	seuil DOUBLE PRECISION NOT NULL, 
	risque_depart BOOLEAN NOT NULL, 
	calculee_le TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (entree_id, version_modele), 
	CONSTRAINT probabilite_entre_0_et_1 CHECK (probabilite BETWEEN 0 AND 1), 
	FOREIGN KEY(entree_id) REFERENCES entrees (id) ON DELETE CASCADE, 
	FOREIGN KEY(version_modele) REFERENCES modeles (version)
);

CREATE INDEX ix_predictions_risque_depart ON predictions (risque_depart);

CREATE INDEX ix_predictions_version_modele ON predictions (version_modele);

-- Droits d'accès, pour une base nommée attrition. Le rôle est créé avec son
-- mot de passe par : uv run python -m attrition_api.create_db --roles
REVOKE ALL ON DATABASE "attrition" FROM PUBLIC;
GRANT CONNECT ON DATABASE "attrition" TO "api_attrition";
GRANT USAGE ON SCHEMA public TO "api_attrition";
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM "api_attrition";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM "api_attrition";
GRANT SELECT, INSERT ON "modeles", "entrees", "predictions" TO "api_attrition";
GRANT SELECT ("id", "departement", "age", "genre", "revenu_mensuel", "statut_marital", "poste", "nombre_experiences_precedentes", "annee_experience_totale", "annees_dans_l_entreprise", "annees_dans_le_poste_actuel", "satisfaction_employee_environnement", "note_evaluation_precedente", "satisfaction_employee_nature_travail", "satisfaction_employee_equipe", "satisfaction_employee_equilibre_pro_perso", "note_evaluation_actuelle", "heure_supplementaires", "augementation_salaire_precedente", "nombre_participation_pee", "nb_formations_suivies", "distance_domicile_travail", "niveau_education", "domaine_etude", "frequence_deplacement", "annees_depuis_la_derniere_promotion", "annes_sous_responsable_actuel") ON employes TO "api_attrition";
GRANT USAGE ON SEQUENCE "entrees_id_seq", "predictions_id_seq" TO "api_attrition";
