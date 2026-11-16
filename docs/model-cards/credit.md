# Fiche modèle — sba_credit_chargeoff

## Usage et population

- Événement : loan_charge_off
- Horizon : historical_resolved_loan_outcome_unspecified
- Version enregistrée : 1
- Famille sélectionnée sur validation : forest
- Entrées : GrAppv, SBA_Appv, guarantee_ratio, NoEmp, NAICS2, NewExist, State, UrbanRural, LowDoc, RevLineCr
- Entraînement : 527575 lignes ; test final : 178670 lignes.
- Calibration sigmoïde retenue : True

## Évaluation finale

| Mesure | Validation | Test |
|---|---:|---:|
| roc_auc | 0.658344 | 0.662284 |
| pr_auc_average_precision | 0.402291 | 0.451339 |
| precision | 0.288863 | 0.344794 |
| recall | 0.999979 | 0.988492 |
| f1 | 0.448243 | 0.511258 |
| brier | 0.206046 | 0.247125 |
| prevalence | 0.274424 | 0.330229 |
| threshold | 0.041554 | 0.041554 |
| simulated_cost | 0.675634 | 0.658309 |

Matrice test TN/FP/FN/TP : [8838, 110830, 679, 58323].
Intervalles bootstrap descriptifs à 95 % : {"roc_auc": [0.6599251180384785, 0.6649504745430586], "average_precision": [0.4480139322753807, 0.45570039894815995]}

## Méthode

Transformations apprises uniquement sur entraînement ; trois plis internes ; Optuna et pondération de classes. La calibration utilise des prédictions hors pli d'entraînement. Modèle, calibration et seuil choisis sur validation avant ouverture du test. La PR-AUC principale est l'average precision, distincte de l'aire PR calculée par MLlib.

## Limites

- Historically approved and resolved loans only; censoring and selection bias.
- Not a one-year PD or validated pre-approval decision.
- Validation Brier is worse than the prevalence-only baseline; probability accuracy is limited.
- Variation temporelle de prévalence : 9,3 % en entraînement, 27,4 % en validation et 33,0 % sur test. La calibration est insuffisante ; aucune PD bancaire validée n'est revendiquée.
- Term exclu faute de preuve qu'il désigne la durée contractuelle initiale.

## Traçabilité

- Données préparées SHA-256 : `8e57d8cf6253d51f24e53e2b1930f8569126ae9cd17c64312c7b78761d4e1167`
- Identifiants de test SHA-256 : `0d547d79a2ce7627e9e792cf5d6502c14d8638f9a9ceda2192e23ebb363a3674`
- Artefact SHA-256 : `458ce3a789ba732fe5aeb09d4c5a8fdf4d4c3e61b2825e5f6a07fca5e3534791`
- Sources et licences : voir ../DATA_AND_METHODS.md. Aucune conformité Bâle certifiée.
