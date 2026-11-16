# Données, définitions et méthodologie

## Provenance et droits

SBA : neuf fichiers `w06-SBAnational01.csv` à `w06-SBAnational09.csv`,
899 164 lignes, livrés localement par l'utilisateur. La publication primaire est
Li, Mickel et Taylor (2018), DOI https://doi.org/10.1080/10691898.2018.1434342.
Un distributeur portant les noms exacts des fichiers est
https://pengdsci.github.io/datasets/ ; l'identité binaire de ces fichiers avec
une distribution officielle n'est pas supposée. Les empreintes SHA-256 sont
calculées dans `reports/generated/data_audit.json`. La licence exacte de cette
copie reste à établir avant toute redistribution. Aucun CSV brut dans Git.

Polish : UCI dataset 365, Sebastian Tomczak (2016),
https://doi.org/10.24432/C5F600, licence CC BY 4.0 :
https://creativecommons.org/licenses/by/4.0/.
https://www.archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data
Les noms `1year` à `5year` ne sont pas les horizons directement : ils correspondent
respectivement à cinq, quatre, trois, deux et un an. Le projet utilise uniquement
`5year.arff` pour les deux modèles Polish. L'audit couvre les cinq fichiers.

## Audit initial vérifié

SBA : 739 609 PIF, 157 558 CHGOFF, 1 997 cibles absentes ; aucun identifiant de
prêt dupliqué. 4 927 PIF ont une date de charge-off et sont exclus de la cohorte
principale. Les 261 cibles absentes avec une date d'événement ne sont pas réparées
en utilisant cet événement. 47 CHGOFF n'ont pas de date de charge-off : le statut
reste utilisable mais pas une analyse de délai jusqu'à événement.

`Term` varie de 0 à 569 ; `NoEmp` atteint 9 999. Un lien très fort entre durée et
issue ne prouve pas la disponibilité de la durée originale au moment prévu.
Sans preuve documentaire, Term reste exclu des modèles principaux et des entrées
SBA. La durée demandée du formulaire principal ne remplace jamais cette variable.
`GrAppv` désigne un montant approuvé, `SBA_Appv` une garantie approuvée ;
`DisbursementGross` est exclu. Codes non documentés de RevLineCr/LowDoc/NewExist
deviennent UNKNOWN ; la catégorie UrbanRural 0 signifie inconnu dans le contrat.
Le secteur dérive des deux premiers chiffres d'un NAICS historique de six chiffres.

Polish à un an : 5 910 lignes, 410 positifs, 60 occurrences supplémentaires de
profils identiques ; après déduplication, 5 850 profils, dont 408 positifs.
Attr37 manque dans 2 548 lignes avant déduplication. Aucun identifiant de firme ni
date calendaire : une séparation temporelle ou par entreprise ne peut être prouvée.
L'absence d'égalité exacte entre cohortes ne démontre pas l'absence de firmes communes.

## Contrats et dictionnaire

Le dictionnaire exhaustif est généré dans `configs/polish_dictionary.json` depuis
les définitions UCI encodées dans le package. Les conventions de signe, unité
monétaire de Attr55 et base du logarithme Attr29 ne sont pas inventées.
Les libellés UCI de Attr48/49 utilisent une expression d'EBITDA avec une
soustraction de dépréciation : le dictionnaire conserve cet avertissement, sans
recalculer ni corriger les observations historiques.

Attr24 est décrit comme « gross profit (in 3 years) / total assets » sans préciser
explicitement dans les fichiers locaux si l'agrégat est rétrospectif. Le modèle
complet conserve les 64 variables conformément au cahier des charges, mais cette
ambiguïté empêche de certifier l'absence de fuite temporelle résiduelle. Une
validation prospective demanderait une confirmation documentaire de la source.
Le modèle simplifié n'utilise pas cette variable.

`debt_ratio` du formulaire simplifié signifie **passif total / actif total**,
contrairement au ratio dette / fonds propres cité dans le PDF académique.
L'interface affiche la convention explicitement. `current_ratio` signifie actif
courant / passif à court terme. Les six autres champs ne sont jamais prédictifs.
Les 64 valeurs doivent être renseignées pour l'inférence complète ; les médianes
apprises ne servent pas à inventer des champs absents lors de la saisie.

## Splits, calibration et évaluation

Les doublons Polish sont éliminés sur le vecteur complet, puis un seul manifeste
stratifié 60/20/20 est partagé. Le modèle simplifié n'est pas découpé à nouveau.
SBA : partition par date d'approbation, avec frontières de dates entières et purge
des emprunteurs apparaissant dans des partitions ultérieures. Le groupe emprunteur
est une empreinte nom/code postal imparfaite, jamais une caractéristique du modèle.

Toutes les médianes, vocabulaires et normalisations sont ajustés sur entraînement.
Optuna utilise les plis internes (chronologiques SBA, stratifiés Polish). La
calibration sigmoïde utilise des prédictions hors pli d'entraînement ; le choix
brut/calibré utilise Brier sur validation. Sélection : AP validation puis Brier
puis coût simulé. Le seuil minimise FN*10 + FP*1 sur validation, avec hypothèses
configurables. Le test final est évalué après verrouillage de la sélection.
Les intervalles bootstrap sont descriptifs et n'éliminent pas les biais des données.

La PR-AUC principale est `average_precision_score`. L'aire PR MLlib utilise une
autre convention : son libellé est distinct et aucune comparaison numérique
directe trompeuse n'est faite. SHAP explique le modèle de base sur son échelle
native ; la transformation de calibration est indiquée séparément.

## Limites de portée

SBA représente des prêts approuvés et des issues résolues ; l'absence de suivi
certifié empêche d'affirmer une PD à un an ou une correction complète de censure.
La dernière date de charge-off ne constitue pas une date d'extraction.
Les cohortes anciennes ne garantissent pas de performance sur les PME actuelles,
au Maroc ou dans d'autres populations. Aucun rapprochement de lignes ni moyenne
des probabilités des trois modèles. Aucune conformité Bâle revendiquée.
