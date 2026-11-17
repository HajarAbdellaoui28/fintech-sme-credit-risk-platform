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

## Correction de la CI — vérification du 17 novembre 2026

`constraints.txt` épinglait déjà setuptools 84.2.1, mais une contrainte ne demande
pas l'installation d'un paquet. La dépendance `[build-system]` est installée dans
l'environnement de compilation isolé de pip, distinct de celui que `pip-audit`
inspecte. Un setuptools 79.0.1 préexistant pouvait donc rester installé.
L'origine exacte du 79.0.1 du runner ne peut pas être certifiée sans ses journaux
d'installation ; rien dans le dépôt ne demande explicitement cette version.

Une reproduction minimale dans une `.venv` temporaire confirme : 79.0.1 avant et
après `pip install -c constraints.txt --no-deps -e .`, puis 84.2.1 après
`pip install --upgrade -c constraints.txt pip setuptools`. Cette expérience isole
le mécanisme et ne prétend pas rejouer l'image GitHub complète.

La CI met désormais explicitement à jour pip et setuptools, applique aussi les
contraintes aux builds isolés, vérifie setuptools 84.2.1 et exécute `pip check`.
L'extra `dev` demande également setuptools >=84.1,<85. Le cache pip est indexé par
`constraints.txt` et `pyproject.toml` ; il ne restaure pas une `.venv` ni les états
DVC. Les deux avis setuptools sont corrigés, pas placés en exception :
PYSEC-2026-3447 nécessite >=83.0.0 ; GHSA-xmj3-9gf7-h52w nécessite >=84.1.0.

Sources : [contraintes pip](https://pip.pypa.io/en/stable/user_guide/#constraints-files),
[isolation des builds](https://pip.pypa.io/en/stable/reference/build-system/),
[avis PYSEC setuptools](https://osv.dev/vulnerability/PYSEC-2026-3447),
[avis setuptools Windows](https://github.com/advisories/GHSA-xmj3-9gf7-h52w).

## DiskCache : correctif indisponible et compatibilité DVC

Métadonnées PyPI consultées le 17 novembre 2026 :

| Paquet | Dernière version publiée | Relation conservée |
|---|---|---|
| DVC | 3.67.1 | dvc-data >=3.18.2,<3.19.0 |
| dvc-data | 3.18.3 | diskcache >=5.2.1 |
| DiskCache | 5.6.3 | Aucun correctif publié ni version corrigée annoncée par pip-audit |

Ces versions restent épinglées dans `constraints.txt`. Aucun remplacement de DVC,
fork, monkeypatch du sérialiseur ou mise à jour ML n'est effectué. Une éventuelle
borne « <5.6.4 » dans une base secondaire ne prouve pas qu'un paquet 5.6.4 existe.

Sources : [DVC/PyPI](https://pypi.org/pypi/dvc/json),
[dvc-data/PyPI](https://pypi.org/pypi/dvc-data/json),
[DiskCache/PyPI](https://pypi.org/pypi/diskcache/json),
[avis PYSEC-2026-2447](https://osv.dev/vulnerability/PYSEC-2026-2447).

### Exposition réelle et mesures de réduction du risque

L'avis PYSEC-2026-2447 (alias CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v) décrit une
exécution de code possible lorsqu'un attaquant écrit dans un cache qui est ensuite
désérialisé avec pickle. `dvc_data.hashfile.cache.Cache` utilise effectivement
DiskCache et pickle pour ses états/index ; intercepter les erreurs pickle ne
supprime pas cette exposition. Le cache d'objets DVC et le cache d'état sérialisé
sont deux stockages distincts : isoler seulement `.dvc/cache` ne suffit pas.

- La CI utilise un runner hébergé éphémère, un `DVC_SITE_CACHE_DIR` dans
  `runner.temp`, créé avec des permissions 0700. Le test DVC utilise aussi ses
  propres caches d'état, d'objets, configurations et remote temporaires. Les
  permissions POSIX privées sont vérifiées par le test.
- Les états/index DVC ne sont ni restaurés avec `actions/cache`, ni téléchargés
  depuis les artefacts d'une PR ou d'un fork. Ne pas partager ces caches avec des
  processus ou identités non fiables. Le cache pip conservé par setup-python est
  distinct des états DiskCache.
- Localement, `core.site_cache_dir` est redirigé vers
  `storage/dvc-site-cache` dans `.dvc/config.local`, ignoré par Git. L'ancien cache
  partagé n'est pas supprimé et les objets, données, modèles et remote sont
  préservés. Pour reproduire ce réglage dans PowerShell :

  ```powershell
  .\.venv\Scripts\dvc.exe config --local core.site_cache_dir "$PWD/storage/dvc-site-cache"
  ```

- L'ACL Windows inspectée autorise HP, SYSTEM/administrateurs et les identités
  d'exécution du bac à sable. Elle n'est pas certifiée « propriétaire seul ».
  Le nouveau dossier hérite des ACL du projet ; aucun droit système global n'est
  modifié. Chaque identité autorisée en écriture doit rester de confiance.
- Les routes de prédiction ne lisent pas de caches DVC fournis par l'utilisateur.
  La condition d'écriture locale préalable reste néanmoins pertinente sur les
  postes, conteneurs ou runners compromis. L'exception ne couvre aucune exposition
  publique, aucun runner partagé non fiable et aucune mise en production bancaire.

**Risque résiduel :** la désérialisation vulnérable subsiste. Un processus compromis
ayant les droits du compte, ou un autre écrivain autorisé, peut empoisonner le
cache et obtenir une exécution lors d'une lecture ultérieure. Les permissions,
l'isolation et les empreintes d'objets ne corrigent pas le code de DiskCache.
Le même principe de confiance s'applique aux fichiers joblib et artefacts MLflow.

### Proposition d'exception temporaire, à examiner avec ce patch

Pour préserver DVC, le patch propose une seule exception de risque dans
`configs/dependency-audit-policy.json` : tuple exact
**diskcache / 5.6.3 / PYSEC-2026-2447**, expiration **17 décembre 2026 à 00:00 UTC**.
Le mainteneur doit examiner ce risque avant publication/fusion du patch ; aucune
approbation de sécurité antérieure ni homologation n'est revendiquée.

Le nouveau contrôle `python -m fintech_risk.dependency_audit` exécute réellement
pip-audit **sans `--ignore-vuln`**. Il conserve le rapport brut et produit une
décision distincte, téléchargeables dans l'artefact GitHub `dependency-security-audit`.
Il ne retourne 0 avec exception que pour ce tuple, avant son expiration et en
l'absence de version corrective indiquée par l'audit. Tout autre paquet, version,
avis, correctif disponible, politique expirée ou erreur d'audit bloque la CI.
La décision indique `pass_with_exception`, jamais une disparition de la faille.

L'audit strict reste disponible :

```powershell
.\.venv\Scripts\python.exe -m fintech_risk.dependency_audit --strict --output reports/generated/ci-security-strict-audit.json
```

Il retourne actuellement 1 pour DiskCache ; le contrôle proposé avec exception
retourne 0. Le fournisseur rapporte deux enregistrements identiques pour un seul
avis/paquet ; ils restent tous deux visibles. Le package local éditable est la
seule distribution explicitement exclue de l'interrogation PyPI.

À chaque mise à jour DVC/dvc-data/DiskCache ou annonce d'un correctif : tester
l'upgrade, retirer l'exception si possible et refaire audit, `pip check`, Pytest et
les contrôles DVC. L'expiration doit conduire à une revue, pas à un renouvellement
automatique. Sans acceptation de cette proposition, conserver le mode strict et
son blocage tant qu'un correctif compatible n'existe pas.

### Résultats exécutés après modification

| Contrôle | Résultat vérifié le 17 novembre 2026 |
|---|---|
| setuptools installé | 84.2.1 ; aucun des deux avis signalés |
| pip-audit brut / mode strict | Sortie 1 ; seul PYSEC-2026-2447, deux enregistrements identiques |
| Contrôle avec exception proposée | Sortie 0 ; `pass_with_exception`, aucun autre avis accepté |
| `pip check` | Réussi sous Windows et dans le conteneur Linux |
| Pytest complet Windows | 39 réussis, 0 échec, 0 ignoré |
| Tests ciblés Linux | 10 réussis ; cycle DVC réel et permissions privées vérifiés |
| Ruff / Bandit | Réussis ; aucun problème moyen/élevé Bandit |
| Workflow modifié | actionlint 1.7.12 : sortie 0 |
| DVC du projet | État à jour, remote synchronisé, reproduction `--dry` sans exécution |
| Modèles | Empreintes des trois champions version 1 vérifiées ; aucun réentraînement |

Les preuves sont conservées dans `reports/generated/ci-security-*.json`, les
rapports JUnit `ci-security-tests.xml` / `ci-security-linux-tests.xml` et le journal
`ci-security-actionlint.log`. La reproduction du mécanisme setuptools figure dans
`ci-setuptools-repro.json`. Aucun push ni lancement GitHub distant n'a été effectué.

Aucune exposition publique ni mise en production bancaire n'est autorisée ou
revendiquée. Les fonctionnalités GitHub/cloud configurées ne sont pas présentées
comme exécutées à distance.
