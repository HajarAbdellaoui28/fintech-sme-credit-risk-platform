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
- **PYSEC-2026-2447 / DiskCache 5.6.3 : aucun correctif proposé ; le contrôle CI
  strict des dépendances reste en échec.** L'avis n'est pas ignoré.
- Le remote DVC est local et ne protège pas contre la perte du même disque.

Preuves : `reports/generated/`. Les résultats synthétiques des tests ne sont
jamais substitués aux évaluations sur les jeux réels.
