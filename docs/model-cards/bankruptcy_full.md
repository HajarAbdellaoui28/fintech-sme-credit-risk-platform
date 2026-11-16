# Fiche modèle — polish_bankruptcy_full_1y

## Usage et population

- Événement : corporate_bankruptcy
- Horizon : 1_year
- Version enregistrée : 1
- Famille sélectionnée sur validation : xgboost
- Entrées : Attr1, Attr2, Attr3, Attr4, Attr5, Attr6, Attr7, Attr8, Attr9, Attr10, Attr11, Attr12, Attr13, Attr14, Attr15, Attr16, Attr17, Attr18, Attr19, Attr20, Attr21, Attr22, Attr23, Attr24, Attr25, Attr26, Attr27, Attr28, Attr29, Attr30, Attr31, Attr32, Attr33, Attr34, Attr35, Attr36, Attr37, Attr38, Attr39, Attr40, Attr41, Attr42, Attr43, Attr44, Attr45, Attr46, Attr47, Attr48, Attr49, Attr50, Attr51, Attr52, Attr53, Attr54, Attr55, Attr56, Attr57, Attr58, Attr59, Attr60, Attr61, Attr62, Attr63, Attr64
- Entraînement : 3510 lignes ; test final : 1170 lignes.
- Calibration sigmoïde retenue : True

## Évaluation finale

| Mesure | Validation | Test |
|---|---:|---:|
| roc_auc | 0.955838 | 0.948951 |
| pr_auc_average_precision | 0.770113 | 0.793319 |
| precision | 0.403409 | 0.397727 |
| recall | 0.865854 | 0.864198 |
| f1 | 0.550388 | 0.544747 |
| brier | 0.030188 | 0.029067 |
| prevalence | 0.070085 | 0.069231 |
| threshold | 0.091526 | 0.091526 |
| simulated_cost | 0.183761 | 0.184615 |

Matrice test TN/FP/FN/TP : [983, 106, 11, 70].
Intervalles bootstrap descriptifs à 95 % : {"roc_auc": [0.9253154035586505, 0.9754296967084556], "average_precision": [0.7259430663663188, 0.8670511996599064]}

## Méthode

Transformations apprises uniquement sur entraînement ; trois plis internes ; Optuna et pondération de classes. La calibration utilise des prédictions hors pli d'entraînement. Modèle, calibration et seuil choisis sur validation avant ouverture du test. La PR-AUC principale est l'average precision, distincte de l'aire PR calculée par MLlib.

## Limites

- Historical Polish population; external validity not established.
- Bankruptcy probability is not credit PD.
- Temporalité exacte de l'agrégat Attr24 non certifiée ; absence de fuite temporelle résiduelle non garantie.

## Traçabilité

- Données préparées SHA-256 : `fd0fa96049559690a44b63cc6475b7ccbd577d98195603e772eeea0922962a67`
- Identifiants de test SHA-256 : `0ca2e327f5d8577a76379aaf635a261d922e21e9f05bcff5dcaa8f01a87a047d`
- Artefact SHA-256 : `d7c2195e7695aed6d9607dc3e37b93ae5776fa620286b319425b9e0e8baa3fd2`
- Sources et licences : voir ../DATA_AND_METHODS.md. Aucune conformité Bâle certifiée.
