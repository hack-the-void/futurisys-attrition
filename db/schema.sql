-- Généré par : uv run python -m attrition_api.create_db --sql db/schema.sql

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
	PRIMARY KEY (id)
);

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
