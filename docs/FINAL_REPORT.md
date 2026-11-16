# Rapport final — FinSight

## Périmètre livré

La plateforme locale comprend trois modèles réellement entraînés, évalués et
enregistrés séparément dans MLflow, une API FastAPI, six sections Streamlit,
PostgreSQL, des PDF et un déploiement Docker Compose. Les sources sont modulaires
dans `src/fintech_risk`. Aucun push, publication d'image ou déploiement externe
n'a été effectué.

Le formulaire principal accepte exactement les huit champs de l'énoncé. Seuls
`debt_ratio` et `current_ratio`, selon les définitions comptables affichées,
alimentent Attr2 et Attr4. Les autres valeurs servent aux calculs financiers,
alertes et références. Les probabilités de faillite, de charge-off et les
hypothèses annuelles de crédit restent distinctes. Les grades A–F sont indicatifs.

L'analyse complète offre un import CSV strict de 64 variables, des erreurs par
ligne, un formulaire manuel documenté et trois exemples complets issus de
l'entraînement. Le crédit SBA possède son propre contrat d'entrées, fondé sur des
montants approuvés. Le simulateur et le portefeuille proposent analyses,
segmentation, scoring batch et exports. La sauvegarde des dossiers est volontaire.

## Résultats ML observés

Ces résultats sont ceux des champions initiaux version 1, conservés en service.
Le test n'a pas été utilisé pour régler les modèles.

| Modèle | Algorithme et calibration | Test | ROC-AUC | Average precision | Brier |
|---|---|---:|---:|---:|---:|
| Faillite simplifiée à un an | XGBoost, sigmoid | 1 170 | 0,76004 | 0,28258 | 0,05794 |
| Faillite complète à un an | XGBoost, sigmoid | 1 170 | 0,94895 | 0,79332 | 0,02907 |
| Charge-off SBA historique | Random Forest, sigmoid | 178 670 | 0,66228 | 0,45134 | 0,24712 |

Les deux modèles Polish utilisent exactement les mêmes observations de test.
Le modèle simplifié est nettement moins discriminant que le modèle complet.
Le score SBA a une calibration insuffisante sous changement temporel de
prévalence : son usage comme PD bancaire validée n'est pas justifié.

La préparation traite les 899 164 prêts SBA et les cinq cohortes Polish. Le modèle
à un an utilise exclusivement `5year.arff`, soit 5 850 profils après déduplication.
Le SBA final compte 880 468 observations admissibles, réparties chronologiquement,
avec retrait des emprunteurs communs aux partitions antérieures. Les étapes de
transformation sont apprises sur entraînement uniquement. Optuna compare LR, RF
et XGBoost, puis la validation choisit modèle, calibration et seuil. Le réglage
SBA utilise au maximum 100 000 lignes déterministes ; l'ajustement final utilise
toutes les lignes admissibles d'entraînement. Des références MLlib LR/RF ont
également été exécutées pour les trois tâches.

Les cartes `docs/model-cards/*.md` détaillent précision, rappel, F1, matrices de
confusion, intervalles descriptifs et empreintes. SHAP explique le modèle de base
avant calibration et ne prétend pas fournir des effets causaux.

## Vérification et preuves locales

Les preuves brutes reproductibles se trouvent dans `reports/generated` :

| Contrôle | Preuve |
|---|---|
| Suite finale Pytest : 29 tests réussis | `tests-final.xml` |
| API réelle, trois modèles et PostgreSQL | `live_integration.json` |
| Comportements des six sections Streamlit | `dashboard_behavior.json` |
| Chrome isolé : huit champs, CSV invalide/export, mobile | `browser_checks.json`, `screenshots/` |
| Parité de prédiction Windows/Linux sur le test réel | `preprocessing_parity.json` |
| Dérive Evidently : témoins et perturbations explicites | `drift_verification.json`, `drift/` |
| Réentraînement contrôlé, promotion protégée et rollback | `model_delivery_verification.json` |
| Reproduction DVC et maintien des champions | `reproducibility.json` |
| Services Docker et séparation du runtime Spark | `docker_verification.json`, `training_image_verification.json` |
| Latence réelle, 1 000 requêtes par cas, concurrences 1 et 4 | `latency.json` |
| Audit du code et des dépendances | `security-bandit.json`, `security-dependencies.json` |

Les vérifications d'interface et d'intégration exécutent les modèles réels.
Les petites données synthétiques des tests CI sont réservées aux tests et ne
remplacent jamais les résultats empiriques ci-dessus. Les chiffres de latence
doivent être lus avec les conditions du JSON : local, connexions persistantes,
modèles chauds, SHAP SME mis en cache, aucune garantie à froid.

Mesures finales de p95, en millisecondes ; **aucune erreur HTTP sur les 6 000
requêtes mesurées** :

| Modèle | Modèle seul | API, concurrence 1 | API, concurrence 4 |
|---|---:|---:|---:|
| Faillite simplifiée | 8,58 | 49,56 | 142,60 |
| Faillite complète | 11,38 | 25,53 | 104,63 |
| Charge-off SBA | 27,94 | 40,04 | 397,46 |

La cible p95 de 100 ms est atteinte pour les modèles seuls et les routes API
séquentielles dans ces conditions locales. Elle **n'est pas atteinte à quatre
requêtes simultanées**. Aucune garantie générale de latence n'est revendiquée.
L'optimisation précharge les bornes de référence et limite les threads imbriqués ;
elle ne met pas les prédictions en cache et ne modifie pas les poids appris.

## MLOps et reproductibilité

DVC suit les 14 fichiers bruts, les données préparées et des instantanés de modèles
dans `data/model-snapshots`. Les artefacts vivants et le manifeste servi restent
hors des sorties DVC. Une reproduction enregistre des candidats sans changer les
champions. Le remote est local et ne protège pas contre une perte du disque.

La première répétition intégrale a révélé un défaut de propriété des sorties DVC :
elle pouvait supprimer les artefacts servis avant de les recréer. Les champions
initiaux ont été récupérés depuis les copies MLflow et vérifiés par empreinte.
Le pipeline a été corrigé, un test de non-recouvrement ajouté et une nouvelle
reproduction complète effectuée. Les événements de récupération restent audités.

Un candidat de réentraînement simplifié a été créé sur la validation gelée, sans
ouvrir à nouveau le test final. Une promotion authentifiée puis un rollback ont
été exécutés. La dérive compare seulement les entrées ; les exemples perturbés
sont étiquetés comme démonstrations et n'entraînent aucune promotion automatique.

## Configuré seulement et actions opérateur

Les workflows GitHub de CI, livraison d'image et livraison de modèles existent.
Leurs contrôles disponibles ont été exécutés localement ; aucune exécution
GitHub distante n'est revendiquée. Il reste à configurer un dépôt distant, les
environnements protégés, les secrets et un runner Windows muni du label
`fintech-local`. `FINTECH_WORKSPACE` doit pointer vers un projet préparé hors du
checkout du runner. Toute publication nécessite une autorisation distincte.

L'admission de données nouvelles exige des preuves de provenance et de maturité
des labels. Elle est implémentée, mais aucune nouvelle cohorte externe authentifiée
n'a été fournie ; ce scénario de production n'a donc pas été exécuté. Les
sauvegardes hors disque, la gestion d'identités multi-utilisateur, TLS et une
validation bancaire externe relèvent d'une future exploitation autorisée.

## Limites et sécurité

- SBA : sélection des prêts approuvés et résolus, date d'extraction non certifiée,
  censure résiduelle et dérive temporelle. `Term` est exclu faute de preuve qu'il
  désigne la durée contractuelle d'origine disponible au point de décision.
- Polish : pas d'identifiant d'entreprise permettant de certifier l'absence de
  firmes communes. La temporalité des trois années d'Attr24 reste ambiguë ;
  l'absence totale de fuite temporelle du modèle à 64 variables n'est pas certifiée.
- Les unités et conventions comptables non documentées ne sont pas inventées.
  La licence exacte des copies SBA doit être consolidée avant redistribution.
- Les probabilités de faillite ne servent jamais de PD de crédit au calcul EL.
  PD, LGD, EAD et taux simulés restent des hypothèses explicites.
- Secrets ignorés par Git, ports loopback, schémas stricts, logs sans données
  financières et empreintes d'artefacts de confiance. Les empreintes ne protègent
  pas contre un attaquant contrôlant simultanément le manifeste et le stockage.
- Bandit ne relève pas de problème moyen/élevé. L'audit des dépendances conserve
  **PYSEC-2026-2447 sur DiskCache 5.6.3, sans correctif proposé**. Le contrôle CI
  strict reste en échec, sans exception ni masquage. Voir `docs/SECURITY.md`.

## Utilisation locale

Les services se lancent avec `docker compose up -d`, après préparation des données
et présence des champions. Leurs adresses sont :

- Interface : http://localhost:8501
- Documentation API : http://localhost:8000/docs
- MLflow : http://localhost:5001

Le profil `training` sépare Java/Spark des services d'inférence et limite les
ressources. Les commandes détaillées, contrats, sauvegardes et procédures de
promotion se trouvent dans le README et `docs/DEPLOYMENT.md`.
