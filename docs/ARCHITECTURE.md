# Architecture finale approuvée

Trois modèles indépendants : `polish_bankruptcy_simplified_1y` (Attr2, Attr4),
`polish_bankruptcy_full_1y` (Attr1..Attr64), `sba_credit_chargeoff`.
Les deux modèles Polish partagent les mêmes identifiants et partitions issus de
`5year.arff` ; aucun regroupement des cinq horizons. La comparaison porte sur
exactement le même test. La cible SBA porte sur les prêts historiquement approuvés
et résolus ; elle n'est ni une probabilité annuelle ni une faillite.

Le formulaire principal contient exactement huit champs. `debt_ratio` signifie
passif total / actif total et `current_ratio` actif courant / passif court terme.
Seuls ces deux ratios entrent dans le modèle simplifié. Les autres champs servent
aux calculs financiers, alertes, simulations et références de dossier.
La probabilité de faillite n'alimente jamais le calcul de perte de crédit.

PySpark valide et prépare les données, puis exporte en Parquet. Les pipelines
scikit-learn/XGBoost portables encapsulent les transformations apprises et la
calibration. Des références MLlib complètent la comparaison académique. FastAPI
charge des versions fixes au démarrage, sans Spark ni entraînement. Streamlit
communique uniquement via HTTP avec l'API et propose six sections.

PostgreSQL persiste les portefeuilles, dossiers enregistrés volontairement et
événements de gestion ; MLflow utilise sa propre base. DVC suit les données et
étapes ; le remote local persistant reste configurable. Evidently compare les
entrées, sans prétendre mesurer une baisse de performance sans labels observés.
Promotion et rollback sont explicites, authentifiés et audités.

Les trois étapes autonomes sont : 1) données, ML et fondations MLOps ;
2) FastAPI, six sections Streamlit, PDF et Compose ; 3) CI/CD, dérive,
réentraînement contrôlé, benchmarks et vérification complète.

Les sorties DVC de modèles résident exclusivement dans `data/model-snapshots`.
Le magasin vivant `artifacts` et le manifeste de déploiement ne sont jamais des
sorties DVC : une reproduction peut remplacer ses instantanés sans supprimer les
champions servis. L'entraînement DVC enregistre des candidats et contrôle que le
manifeste et les alias champions restent inchangés. Le bootstrap initial explicite
et la promotion administrateur sont des opérations distinctes.

Limites connues : censure SBA, sélection des seuls prêts approuvés, définitions de
Term non garanties à l'origine, absence d'identifiants d'entreprise Polish,
conventions comptables UCI parfois ambiguës. Term reste exclu du modèle principal
sans preuve qu'il s'agit de la durée contractuelle d'origine. Les 64 variables
restent exigées pour le modèle complet ; pas de reconstruction arbitraire.

Aucun déploiement externe, push GitHub, Prometheus ou Grafana.
