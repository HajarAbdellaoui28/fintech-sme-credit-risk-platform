# Fiche modèle — polish_bankruptcy_simplified_1y

## Usage et population

- Événement : corporate_bankruptcy
- Horizon : 1_year
- Version enregistrée : 1
- Famille sélectionnée sur validation : xgboost
- Entrées : Attr2, Attr4
- Entraînement : 3510 lignes ; test final : 1170 lignes.
- Calibration sigmoïde retenue : True

## Évaluation finale

| Mesure | Validation | Test |
|---|---:|---:|
| roc_auc | 0.779490 | 0.760041 |
| pr_auc_average_precision | 0.296033 | 0.282580 |
| precision | 0.289773 | 0.217143 |
| recall | 0.621951 | 0.469136 |
| f1 | 0.395349 | 0.296875 |
| brier | 0.057227 | 0.057936 |
| prevalence | 0.070085 | 0.069231 |
| threshold | 0.126656 | 0.126656 |
| simulated_cost | 0.371795 | 0.484615 |

Matrice test TN/FP/FN/TP : [952, 137, 43, 38].
Intervalles bootstrap descriptifs à 95 % : {"roc_auc": [0.7004340800667768, 0.8214379377742307], "average_precision": [0.1951174056588113, 0.3860286560725719]}

## Méthode

Transformations apprises uniquement sur entraînement ; trois plis internes ; Optuna et pondération de classes. La calibration utilise des prédictions hors pli d'entraînement. Modèle, calibration et seuil choisis sur validation avant ouverture du test. La PR-AUC principale est l'average precision, distincte de l'aire PR calculée par MLlib.

## Limites

- Historical Polish population; external validity not established.
- Bankruptcy probability is not credit PD.
- Deux ratios seulement ; les six autres champs du formulaire ne modifient jamais la probabilité. Performance inférieure au modèle complet sur le même test.

## Traçabilité

- Données préparées SHA-256 : `fd0fa96049559690a44b63cc6475b7ccbd577d98195603e772eeea0922962a67`
- Identifiants de test SHA-256 : `0ca2e327f5d8577a76379aaf635a261d922e21e9f05bcff5dcaa8f01a87a047d`
- Artefact SHA-256 : `22b8b2c9cf729838746c83e27fdbbb23b6b9e28a89ff14b5159a13ffe7c5328a`
- Sources et licences : voir ../DATA_AND_METHODS.md. Aucune conformité Bâle certifiée.
