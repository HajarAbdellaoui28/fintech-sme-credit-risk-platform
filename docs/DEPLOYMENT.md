# Déploiement local et livraison contrôlée

## Isolation locale

Docker Compose nomme ses ressources `fintech-sme` et ne modifie pas les autres
conteneurs. PostgreSQL utilise le port local 5433, MLflow 5001, FastAPI 8000 et
Streamlit 8501. Les ports sont liés à 127.0.0.1. Ne pas utiliser les secrets
d'exemple ; `scripts/setup_local.py` crée des secrets aléatoires dans `.env` ignoré.

Le profil permanent ne démarre jamais Spark ni un entraînement. Le profil
`training` installe Java 17 et PySpark, avec deux CPU et 5 Gio maximum. Arrêter le
dashboard/API pendant les entraînements lourds si nécessaire, en conservant
PostgreSQL et MLflow. Ne pas lancer plusieurs entraînements en parallèle.

L'inférence limite chaque estimateur à un thread pour éviter les pools imbriqués
sur les requêtes individuelles concurrentes. Les poids et transformations appris
restent identiques. Les bornes de référence et seuils de grades sont chargés au
démarrage ; après modification de `params.yaml`, reconstruire l'image et redémarrer
l'API pour appliquer cette configuration. Les prédictions ML ne sont pas mises
en cache ; seuls les calculs SHAP répétés disposent d'un cache local borné.

Les modèles sont des fichiers Python sérialisés de confiance : l'API vérifie les
empreintes du manifeste local, pas une signature cryptographique externe. Ne pas
importer un fichier joblib non fiable. La compromission du manifeste et du stockage
reste hors de la garantie d'intégrité offerte ici.

## Données et sauvegarde

DVC utilise initialement `storage/dvc-remote` comme remote local persistant,
distinct de `.dvc/cache`. Ce remote ne protège pas contre la perte du même disque.
Pour une sauvegarde réelle, configurer un chemin externe ou stockage objet ; ne
jamais ajouter des secrets à `.dvc/config`. La configuration locale est ignorée.
Sauvegarder aussi PostgreSQL et les artefacts MLflow via une procédure opérateur.

## Livraison des modèles

L'approbation initiale autorise le premier champion de chaque tâche, à partir
d'entraînements complets admissibles. Les petits entraînements de développement
ne peuvent pas être promus. Un réentraînement produit un candidat indépendant,
sans mise à jour automatique du champion. La comparaison de qualification utilise
la validation gelée ; le test final ne doit pas servir à itérer sur les promotions.

La promotion vérifie les caractéristiques, l'horizon, l'AP, Brier et le coût.
Elle nécessite le secret administrateur et un motif ; l'événement est journalisé.
Le manifeste déployé conserve la version précédente pour rollback.
L'API recharge les modèles après une promotion effectuée via ses routes de gestion.
Après une promotion CLI, redémarrer l'API pour appliquer la nouvelle version.

## GitHub et cloud

La CI contrôle qualité, tests, sécurité et construction Docker sans données réelles.
La livraison d'image est manuelle et protégée par l'environnement GitHub
`delivery-approval`. Le workflow modèles requiert un runner local explicitement
configuré, sa `.venv`, ses données DVC, l'accès MLflow et l'environnement protégé
`model-approval`. Aucun accès distant ne peut être considéré vérifié localement.
La variable GitHub `FINTECH_WORKSPACE` désigne un projet préparé par l'opérateur,
hors du checkout du runner ; le workflow ne nettoie jamais ce projet avec
`actions/checkout`. Le secret `FINTECH_ADMIN_TOKEN` autorise les promotions.

Un hébergement cloud éventuel utilise les mêmes images, PostgreSQL géré, stockage
objet privé, TLS et gestionnaire de secrets. Le fournisseur, le budget, l'accès et
les autorisations doivent être configurés avant tout déploiement externe.
Aucune ressource cloud, image publiée ni push GitHub n'est créé automatiquement.
