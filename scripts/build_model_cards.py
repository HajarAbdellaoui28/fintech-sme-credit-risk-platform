"""Generate French model cards directly from executed, versioned evaluations."""

import json

from fintech_risk.config import MODEL_NAMES, ROOT, read_json

manifest = read_json(ROOT / "artifacts/deployment.json")
for task, name in MODEL_NAMES.items():
    source = ROOT / manifest[task]["path"] / "metadata.json"
    model = read_json(source)
    test = model["test"]
    lines = [
        f"# Fiche modèle — {name}",
        "",
        "## Usage et population",
        "",
        f"- Événement : {model['predicted_event']}",
        f"- Horizon : {model['horizon']}",
        f"- Version enregistrée : {model.get('registry_version', 'non enregistrée')}",
        f"- Famille sélectionnée sur validation : {model['winner']}",
        f"- Entrées : {', '.join(model['features'])}",
        f"- Entraînement : {model['train_rows']} lignes ; test final : {test['rows']} lignes.",
        f"- Calibration sigmoïde retenue : {model['calibrated']}",
        "",
        "## Évaluation finale",
        "",
        "| Mesure | Validation | Test |",
        "|---|---:|---:|",
    ]
    for key in [
        "roc_auc",
        "pr_auc_average_precision",
        "precision",
        "recall",
        "f1",
        "brier",
        "prevalence",
        "threshold",
        "simulated_cost",
    ]:
        lines.append(f"| {key} | {model['validation'][key]:.6f} | {test[key]:.6f} |")
    lines += [
        "",
        f"Matrice test TN/FP/FN/TP : {test['confusion_matrix_tn_fp_fn_tp']}.",
        "Intervalles bootstrap descriptifs à 95 % : " + json.dumps(test["bootstrap_95ci"]),
        "",
        "## Méthode",
        "",
        "Transformations apprises uniquement sur entraînement ; trois plis internes ; Optuna et pondération de classes. La calibration utilise des prédictions hors pli d'entraînement. Modèle, calibration et seuil choisis sur validation avant ouverture du test. La PR-AUC principale est l'average precision, distincte de l'aire PR calculée par MLlib.",
        "",
        "## Limites",
        "",
    ]
    lines += [f"- {warning}" for warning in model["warnings"]]
    if task == "sme":
        lines.append(
            "- Deux ratios seulement ; les six autres champs du formulaire ne modifient jamais la probabilité. Performance inférieure au modèle complet sur le même test."
        )
    if task == "credit":
        lines += [
            "- Variation temporelle de prévalence : 9,3 % en entraînement, 27,4 % en validation et 33,0 % sur test. La calibration est insuffisante ; aucune PD bancaire validée n'est revendiquée.",
            "- Term exclu faute de preuve qu'il désigne la durée contractuelle initiale.",
        ]
    lines += [
        "",
        "## Traçabilité",
        "",
        f"- Données préparées SHA-256 : `{model['data_sha256']}`",
        f"- Identifiants de test SHA-256 : `{model['test_ids_sha256']}`",
        f"- Artefact SHA-256 : `{model['model_sha256']}`",
        "- Sources et licences : voir ../DATA_AND_METHODS.md. Aucune conformité Bâle certifiée.",
    ]
    output = ROOT / "docs/model-cards" / f"{task}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Three model cards generated from real evaluation metadata.")
