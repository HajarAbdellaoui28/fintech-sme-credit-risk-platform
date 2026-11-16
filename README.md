# FinSight — FinTech SME Credit Risk Analytics Platform

Prototype académique complet d'aide à l'analyse financière des PME. Trois modèles
indépendants : faillite à un an simplifiée (Attr2/Attr4), faillite à un an complète
(64 variables Polish) et charge-off historique d'un prêt SBA approuvé.

**Faillite, défaut de crédit et charge-off ne sont pas interchangeables.** Les
simulations financières restent distinctes des probabilités ML. Aucune conformité
Bâle ni décision de prêt automatique n'est revendiquée.

## Démarrage Windows / PowerShell

Python 3.11, Java 17, Docker Desktop WSL2 et Git sont requis. Les données fournies
restent dans `data/raw/sba` (neuf CSV) et `data/raw/polish` (cinq ARFF), hors Git.

```powershell
.\scripts\bootstrap.ps1
docker compose up -d postgres
# Dans un terminal dédié : registre MLflow local avec son stockage PostgreSQL
.\.venv\Scripts\python.exe scripts/start_mlflow.py
```

Dans un autre terminal, depuis la racine :

```powershell
.\.venv\Scripts\Activate.ps1
fintech prepare
fintech train --task all --trials 10
fintech compare
fintech mllib
```

Ces commandes sont coûteuses et séquentielles. `--limit` est réservé aux essais de
développement et interdit la promotion initiale de leurs résultats. Un entraînement
normal utilise toutes les lignes admissibles d'entraînement ; le réglage SBA peut
utiliser un sous-ensemble déterministe clairement tracé.

Une fois les trois champions enregistrés, arrêter le MLflow du terminal, puis :

```powershell
docker compose build
docker compose up -d
docker compose ps
```

- Dashboard : http://localhost:8501
- API et OpenAPI : http://localhost:8000/docs
- Santé : http://localhost:8000/health
- MLflow : http://localhost:5001

Si Spark natif Windows ne fonctionne pas, utiliser le profil Linux dédié :

```powershell
docker compose --profile training build training
docker compose --profile training run --rm training fintech prepare
```

## Formulaire principal

```json
{"sme_id":"PME-8842","sector":"Services","annual_revenue":4500000.0,"debt_ratio":0.42,"current_ratio":1.85,"requested_amount":500000.0,"loan_term_months":36,"past_defaults":0}
```

`POST /predict/sme` valide exactement ces huit champs et renvoie une vraie
prédiction ML et SHAP. `debt_ratio` = passif total / actif total ; `current_ratio` =
actif courant / dettes à court terme. Les six autres champs influencent uniquement
les analyses, alertes, références et simulations. Toute PD annuelle, LGD, EAD ou
tarification simulée nécessite des hypothèses explicites indépendantes.

## Interface

Six sections : évaluation PME, analyse financière avancée (CSV, 64 champs manuels,
exemples documentés), crédit SBA, simulateur financier, portefeuille et gestion MLOps.
Les PDF précisent le modèle, sa version, l'événement, l'horizon et les limites.
Les dossiers ne sont enregistrés que sur demande explicite.

## Vérifications

```powershell
ruff check .
ruff format --check .
pytest -q
pip check
bandit -r src dashboard scripts -ll
pip-audit --skip-editable
```

Les fixtures CI sont petites et synthétiques, mais entraînent de vrais modèles ;
elles ne sont jamais présentées comme des résultats empiriques finaux. Les résultats
réels, preuves d'exécution et limites sont consignés dans `reports/generated` et
`docs/IMPLEMENTATION_STATUS.md`.

## DVC, dérive et réentraînement

```powershell
dvc status
dvc repro
fintech drift --task sme --current data/current/sme.csv
fintech retrain --task sme --trials 10
```

Le fichier de dérive doit contenir exactement les entrées du modèle (Attr2/Attr4
pour `sme`). Un lot inférieur à 200 lignes est signalé comme insuffisant. La dérive
des entrées ne démontre pas une baisse de performance et ne promeut aucun modèle.
Les candidats sont promus explicitement via l'interface protégée ou
`scripts/manage_model.py`, avec rollback disponible.

`dvc repro` produit des instantanés détachés dans `data/model-snapshots` et des
candidats MLflow. Il ne modifie pas les champions ni le manifeste servi.
Le magasin `artifacts` reste indépendant des sorties remplaçables de DVC.

## Documentation

- [Architecture finale](docs/ARCHITECTURE.md)
- [Données, dictionnaires et méthodologie](docs/DATA_AND_METHODS.md)
- [Déploiement, sécurité et livraison](docs/DEPLOYMENT.md)
- [Suivi d'exécution](docs/IMPLEMENTATION_STATUS.md)
- [Rapport final en français](docs/FINAL_REPORT.md)
- [Sécurité et avis non corrigé](docs/SECURITY.md)

Les workflows GitHub sont configurés localement. Leur exécution distante,
publication d'images et déploiement externe nécessitent configuration et
autorisation ; aucun résultat distant ne peut être déduit d'un contrôle local.
