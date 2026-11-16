# Sécurité et limites connues

Les secrets locaux sont générés dans `.env`, ignorés par Git. Les ports restent
sur loopback. L'API ne charge que des artefacts du stockage local de confiance,
dont elle vérifie l'empreinte. Les opérations de promotion/rollback exigent le
secret administrateur, un candidat admissible et un motif auditable. Les dossiers
et portefeuilles sont sauvegardés uniquement sur action explicite.

Les journaux applicatifs excluent les charges utiles et paramètres de requête.
Ils contiennent route normalisée, statut, durée et identifiant technique aléatoire.
Les données historiques publiques et les entrées utilisateur ne sont pas envoyées
à un service externe d'analyse.

## Contrôles exécutés

Bandit ne signale pas de problème moyen/élevé dans le périmètre contrôlé.
L'audit initial a identifié des versions vulnérables de Arrow, Spark et setuptools.
Les versions correctives retenues sont Arrow 23.0.1, Spark 3.5.8 et setuptools
84.2.1 ; la compatibilité est vérifiée après mise à jour.

## Avis non corrigé en amont

`PYSEC-2026-2447` concerne DiskCache 5.6.3, dépendance transitive de l'outillage.
L'avis indique un risque d'exécution via désérialisation pickle si un attaquant peut
écrire dans le répertoire de cache. Aucune version corrigée n'est proposée par
l'audit au moment de la vérification. Les caches restent privés au compte local et
ne doivent jamais être alimentés depuis un stockage partagé non fiable.

Cet avis n'est pas ignoré dans la CI : **le contrôle strict des dépendances reste
en échec tant qu'un correctif ou une décision de risque explicite n'existe pas**.
Les résultats de tests fonctionnels ne constituent pas une validation de sécurité.
Le même principe de confiance s'applique aux fichiers joblib et artefacts MLflow.

Aucune exposition publique ni mise en production bancaire n'est autorisée ou
revendiquée. Les fonctionnalités GitHub/cloud configurées ne sont pas présentées
comme exécutées à distance.
