# CI et livraison

[ci.yml](../.github/workflows/ci.yml) tourne sur les pushs et les pull requests vers `main`.
Les trois jobs doivent passer pour fusionner une PR.

- **Lint** exécute Ruff et vérifie que les exports `requirements*.txt` correspondent à `uv.lock`.
- **Tests** lance pytest avec une couverture minimale de 80 %, puis vérifie la configuration
  avec `APP_ENV=test`. Le rapport HTML et XML est disponible dans les artefacts du job.
- **Secrets** lance Gitleaks sur les commits envoyés. GitHub bloque aussi l'envoi des secrets
  qu'il reconnaît.

Avant de fusionner, mettre la branche à jour avec `main` et résoudre les conversations de la PR.
Ce projet est individuel et aucune approbation de revue n'est exigée. Le 6 novembre 2026,
les jobs prenaient environ dix secondes chacun une fois démarrés. Refaire la mesure après
l'ajout du modèle et de l'API. La mission fixe un seuil de dix minutes.

## Variables et secrets

| Environnement | Configuration |
| --- | --- |
| Local | `APP_ENV=dev` dans `.env`. Utiliser `.env.example` comme point de départ. |
| GitHub `test` | Variable `APP_ENV=test`. Les tests utilisent leurs propres valeurs. |
| GitHub `production` | Variable `APP_ENV=prod` et secrets `API_KEY`, `DATABASE_URL`. |

Pour générer une clé et l'enregistrer dans GitHub sans l'afficher, utiliser la commande suivante.

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" | gh secret set API_KEY --env production
```

Seul le job de publication dispose de `contents: write`, pour créer la release avec le
`GITHUB_TOKEN` fourni par GitHub. Les actions externes à GitHub sont référencées par SHA.

## Publier une version

[cd.yml](../.github/workflows/cd.yml) se déclenche sur un tag `vX.Y.Z`. Il vérifie que le
commit appartient à `main` et que le tag correspond à la version dans `pyproject.toml`.
Il lance les tests et construit le paquet. Le job de publication passe ensuite par
l'environnement GitHub `production`, réservé aux tags `v*`. Il contrôle les secrets puis
joint le paquet à une GitHub Release. Le déploiement local sera ajouté avec l'API.

Préparer la version sur une branche, puis ouvrir une PR.

```bash
git switch -c chore/version-X.Y.Z
uv version X.Y.Z
git add pyproject.toml uv.lock
git commit -m "chore: passe en version X.Y.Z"
git push -u origin chore/version-X.Y.Z
gh pr create --fill
```

Après la fusion, poser le tag sur le commit de la version.

```bash
git switch main
git pull --ff-only
git tag -a vX.Y.Z -m "Version X.Y.Z"
git push origin vX.Y.Z
```

Si la publication échoue à cause d'un secret, le corriger puis relancer les jobs en échec
avec `gh run rerun <id> --failed`.
