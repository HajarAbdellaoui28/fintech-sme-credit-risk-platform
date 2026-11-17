# Suivi d'implémentation

Architecture finale intégrée : trois modèles indépendants et six sections, avec
le formulaire principal à huit champs et trois modes d'entrée pour le modèle
Polish complet. Le [rapport final](FINAL_REPORT.md) détaille résultats et limites.

## Exécuté et vérifié

- Audit des 899 164 prêts SBA et des cinq cohortes Polish ; préparation PySpark
  3.5.8, partitions partagées Polish et chronologie SBA avec purge des emprunteurs.
- Trois comparaisons LR/RF/XGBoost avec Optuna, calibration hors pli, sélection
  sur validation, évaluation de test et SHAP ; références MLlib réellement exécutées.
- Trois champions MLflow version 1 : simplifié ROC-AUC 0,7600 / AP 0,2826 ;
  complet 0,9490 / 0,7933 ; SBA 0,6623 / 0,4513.
- Suite finale : 29 tests réussis ; Ruff et vérification des dépendances installées
  réussis. Bandit sans problème moyen/élevé après correction du lecteur XML.
- API réelle, persistance PostgreSQL, trois PDF d'évaluation et 25 contrôles
  d'intégration ; six pages Streamlit avec 14 contrôles de comportement.
- Chrome isolé, CSV à erreurs par ligne/export, parité Windows/Linux, dérive
  Evidently sur témoins et perturbations documentées.
- Candidat de réentraînement avec test final scellé ; promotion authentifiée puis
  rollback réels, champions initiaux restaurés.
- Images Docker applicative et formation construites localement ; dépendances
  corrigées Arrow 23.0.1, Spark 3.5.8 et setuptools 84.2.1.

## Validation finale exécutée

- Pipeline DVC complet répété : différence maximale de métriques égale à zéro
  sur les trois tâches, mêmes identifiants de test, sources et champions inchangés.
  34 fichiers poussés au remote local ; données et pipelines à jour.
- Quatre services Docker démarrés ; calcul Spark réel dans le profil training
  avec Java 17 / Python 3.11.18 / PySpark et JVM Spark 3.5.8 cohérents.
- API optimisée sans modification des poids : 25 contrôles réels, parité native /
  conteneur sur 32 observations par modèle, 29 tests réussis après modification.
- Benchmark : 6 000 requêtes HTTP, zéro erreur. P95 API séquentiel : 49,56 ms
  (PME), 25,53 ms (complet), 40,04 ms (SBA). La cible p95 < 100 ms n'est pas
  atteinte à quatre requêtes simultanées : 142,60 / 104,63 / 397,46 ms.
- Les cinq PDF sont générés à partir des résultats réels, rendus et inspectés
  visuellement ; captures desktop, tableau CSV et mobile vérifiés.
- Code, configuration et documentation conservés dans des commits Git locaux,
  sans données brutes, secrets ou artefacts volumineux et sans push.

## Configuré seulement

- CI et livraisons GitHub : YAML contrôlés localement, sans exécution distante.
- Admission d'une nouvelle cohorte externe : implémentée, sans cohorte nouvelle
  authentifiée disponible. Les preuves de maturité doivent être fournies.
- Publication d'image, hébergement cloud, TLS, identités multi-utilisateur et
  sauvegarde hors disque : actions opérateur futures et autorisations distinctes.

## Limites ouvertes

- Calibration SBA insuffisante et décalage temporel de prévalence ; aucune PD
  annuelle ni validation pour une décision de prêt préalable.
- Temporalité d'Attr24 non certifiée ; pas d'identifiants de firme Polish.
- Licence exacte SBA à consolider avant redistribution des fichiers fournis.
- **PYSEC-2026-2447 / DiskCache 5.6.3 : aucun correctif publié.** L'audit strict
  reste en échec ; le patch du 17 novembre propose une exception exacte, bornée
  et expirante dans le contrôle CI, avec conservation de tous les constats bruts.
- Le remote DVC est local et ne protège pas contre la perte du même disque.

Preuves : `reports/generated/`. Les résultats synthétiques des tests ne sont
jamais substitués aux évaluations sur les jeux réels.

## Correctif CI sécurité — 17 novembre 2026

- Cause identifiée et reproduite dans une `.venv` jetable : l'installation
  contrainte de l'éditable ne remplace pas le setuptools 79.0.1 déjà présent ; le
  bootstrap explicite installe 84.2.1. Le paquet de build isolé ne corrige pas
  l'environnement audité. La provenance précise du 79.0.1 du runner n'a pas été
  confirmée à partir de journaux GitHub distants.
- CI : bootstrap pip/setuptools explicite, contraintes de build, assertion de la
  version installée, `pip check`, cache pip indexé par les fichiers de dépendances,
  état DVC privé dans `runner.temp`, audit brut et décision conservés en artefact.
- PyPI vérifié : DVC 3.67.1, dvc-data 3.18.3, DiskCache 5.6.3 sont toujours les
  dernières versions publiées. Leurs pins sont conservés ; aucun correctif
  compatible disponible n'a été identifié.
- Exception **proposée dans le patch** : uniquement diskcache 5.6.3 /
  PYSEC-2026-2447, jusqu'au 17 décembre 2026 à 00:00 UTC. Publication/fusion du
  patch à examiner par le mainteneur. Ce n'est pas une correction de DiskCache.
  Les tests prouvent qu'un autre paquet/version/avis, un correctif disponible ou
  une politique expirée bloque le contrôle. Aucun avis setuptools n'est accepté.
- Exécuté sous Windows : **39 tests réussis**, `pip check` réussi, Ruff réussi,
  Bandit sans problème moyen/élevé. Aucun test ignoré ou désactivé.
- Exécuté dans un conteneur Linux éphémère : **10 tests réussis** pour la politique
  et le cycle DVC, bootstrap et `pip check` réussis, permissions POSIX privées
  vérifiées. Cela ne constitue pas une exécution distante GitHub Actions.
- Workflow modifié vérifié par **actionlint 1.7.12 : sortie 0**.
- Audit réel : setuptools 84.2.1 sans avis ; un seul avis DiskCache, présent deux
  fois dans la réponse du fournisseur. Audit strict : sortie 1. Contrôle avec la
  proposition d'exception : sortie 0, état explicite `pass_with_exception`.
- DVC réel : ajout, exécution d'une petite étape de copie, push, suppression des
  seuls objets jetables, pull et reproduction inchangée vérifiés en tests. Sur
  le projet : `dvc status` à jour, `dvc repro --dry` sans commande exécutée et
  `dvc status --cloud` synchronisé. `dvc.yaml`, `dvc.lock`, paramètres et code
  d'entraînement restent inchangés ; les empreintes des trois champions version 1
  sont vérifiées. Aucun champion n'a été réentraîné.
- Configuration locale uniquement : état DVC déplacé par configuration vers
  `storage/dvc-site-cache` ; ancien cache conservé, ACL globales non modifiées.
  Les écrivains autorisés dans le projet restent une limite de confiance explicite.
- Aucun push, commit du patch, déploiement ou exécution GitHub distante effectué.

Preuves nouvelles dans `reports/generated/` : `ci-setuptools-repro.json`,
`ci-security-upstream.json`, `ci-security-audit.json` et sa décision,
`ci-security-strict-audit.json` et sa décision, `ci-security-tests.xml`,
`ci-security-linux-tests.xml`, `ci-security-bandit.json`.
Synthèse : `ci-security-verification.json` ; validation du workflow :
`ci-security-actionlint.log`.

L'exposition, les mesures de réduction et le risque résiduel figurent dans
[SECURITY.md](SECURITY.md). L'audit strict demeure l'option sans acceptation de
l'exception proposée.
