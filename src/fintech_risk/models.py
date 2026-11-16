"""Portable training, validation-only selection, calibrated inference and evaluation."""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import optuna
import pandas as pd
from scipy.special import logit
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from fintech_risk.config import MODEL_NAMES, ROOT, parameters, read_json, save_json
from fintech_risk.data import source_fingerprint
from fintech_risk.features import (
    CREDIT_CATEGORICAL,
    CREDIT_FEATURES,
    CREDIT_NUMERIC,
    POLISH_FEATURES,
    SIMPLIFIED_FEATURES,
)


@dataclass
class RiskModel:
    pipeline: Pipeline
    features: list
    task: str
    calibrator: object = None

    def predict_proba(self, frame):
        p = self.pipeline.predict_proba(frame[self.features])[:, 1]
        if self.calibrator is not None:
            p = self.calibrator.predict_proba(logit(np.clip(p, 1e-7, 1 - 1e-7)).reshape(-1, 1))[
                :, 1
            ]
        return np.column_stack([1 - p, p])


def task_features(task):
    return (
        CREDIT_FEATURES
        if task == "credit"
        else (SIMPLIFIED_FEATURES if task == "sme" else POLISH_FEATURES)
    )


def dataset(task, root=ROOT):
    return pd.read_parquet(
        root / "data/processed" / ("sba.parquet" if task == "credit" else "polish.parquet")
    )


def build_pipeline(task, family, settings=None, positive_weight=1.0):
    settings = settings or {}
    numeric = CREDIT_NUMERIC if task == "credit" else task_features(task)
    num = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    transformers = [("numeric", num, numeric)]
    if task == "credit":
        transformers.append(
            (
                "category",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CREDIT_CATEGORICAL,
            )
        )
    prep = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
    if family == "logistic":
        estimator = LogisticRegression(
            C=settings.get("C", 1.0),
            class_weight="balanced",
            max_iter=1500,
            random_state=42,
            solver="lbfgs",
        )
    elif family == "forest":
        estimator = RandomForestClassifier(
            n_estimators=settings.get("n_estimators", 120),
            max_depth=settings.get("max_depth", 10),
            min_samples_leaf=settings.get("min_samples_leaf", 10),
            class_weight="balanced_subsample",
            n_jobs=2,
            random_state=42,
        )
    elif family == "xgboost":
        estimator = XGBClassifier(
            n_estimators=settings.get("n_estimators", 150),
            max_depth=settings.get("max_depth", 4),
            learning_rate=settings.get("learning_rate", 0.06),
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=5.0,
            tree_method="hist",
            n_jobs=2,
            random_state=42,
            scale_pos_weight=positive_weight,
            eval_metric="logloss",
        )
    else:
        raise ValueError(f"Unknown estimator family: {family}")
    return Pipeline([("preprocess", prep), ("estimator", estimator)])


def folds(task):
    return (
        TimeSeriesSplit(3)
        if task == "credit"
        else StratifiedKFold(3, shuffle=True, random_state=42)
    )


def tune(task, family, x, y, trials):
    if not trials:
        return {}

    def objective(trial):
        if family == "logistic":
            settings = {"C": trial.suggest_float("C", 0.01, 10, log=True)}
        elif family == "forest":
            settings = {
                "n_estimators": trial.suggest_int("n_estimators", 80, 160, step=40),
                "max_depth": trial.suggest_int("max_depth", 5, 14),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 25),
            }
        else:
            settings = {
                "n_estimators": trial.suggest_int("n_estimators", 80, 200, step=40),
                "max_depth": trial.suggest_int("max_depth", 2, 6),
                "learning_rate": trial.suggest_float("learning_rate", 0.025, 0.15, log=True),
            }
        scores = []
        for tr, va in folds(task).split(x, y):
            weight = (len(y.iloc[tr]) - y.iloc[tr].sum()) / max(1, y.iloc[tr].sum())
            pipe = build_pipeline(task, family, settings, weight)
            pipe.fit(x.iloc[tr], y.iloc[tr])
            scores.append(average_precision_score(y.iloc[va], pipe.predict_proba(x.iloc[va])[:, 1]))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=trials)
    return study.best_params


def fit_calibration(pipe, task, x, y):
    oof = np.full(len(y), np.nan)
    for tr, va in folds(task).split(x, y):
        fitted = clone(pipe).fit(x.iloc[tr], y.iloc[tr])
        oof[va] = fitted.predict_proba(x.iloc[va])[:, 1]
    valid = np.isfinite(oof)
    calibrator = LogisticRegression(C=1e6, max_iter=1000).fit(
        logit(np.clip(oof[valid], 1e-7, 1 - 1e-7)).reshape(-1, 1), y.iloc[np.flatnonzero(valid)]
    )
    pipe.fit(x, y)
    return calibrator


def choose_threshold(y, probabilities, fn_cost=10.0, fp_cost=1.0):
    thresholds = np.unique(np.r_[0.0, np.quantile(probabilities, np.linspace(0, 1, 201)), 1.0])
    costs = []
    for t in thresholds:
        pred = probabilities >= t
        costs.append(float(np.mean(fn_cost * ((y == 1) & ~pred) + fp_cost * ((y == 0) & pred))))
    index = int(np.argmin(costs))
    return float(thresholds[index]), float(costs[index])


def metrics(y, p, threshold, bootstrap=0):
    policy = parameters()["decision"]
    pred = p >= threshold
    result = {
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc_average_precision": float(average_precision_score(y, p)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, p)),
        "threshold": float(threshold),
        "confusion_matrix_tn_fp_fn_tp": confusion_matrix(y, pred, labels=[0, 1]).ravel().tolist(),
        "prevalence": float(np.mean(y)),
        "rows": len(y),
        "simulated_cost": float(
            np.mean(
                policy["false_negative_cost"] * ((y == 1) & ~pred)
                + policy["false_positive_cost"] * ((y == 0) & pred)
            )
        ),
    }
    if bootstrap:
        rng = np.random.default_rng(42)
        values = []
        ya = np.asarray(y)
        for _ in range(bootstrap):
            idx = rng.integers(0, len(y), len(y))
            if len(np.unique(ya[idx])) == 2:
                values.append(
                    [roc_auc_score(ya[idx], p[idx]), average_precision_score(ya[idx], p[idx])]
                )
        intervals = np.quantile(values, [0.025, 0.975], axis=0)
        result["bootstrap_95ci"] = {
            "roc_auc": intervals[:, 0].tolist(),
            "average_precision": intervals[:, 1].tolist(),
        }
    return result


def evaluation_plots(y, p, directory):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    fpr, tpr, _ = roc_curve(y, p)
    axes[0].plot(fpr, tpr)
    axes[0].plot([0, 1], [0, 1], "--", color="grey")
    axes[0].set(title="ROC", xlabel="False positive rate", ylabel="True positive rate")
    precision, recall, _ = precision_recall_curve(y, p)
    axes[1].plot(recall, precision)
    axes[1].axhline(np.mean(y), ls="--", color="grey")
    axes[1].set(title="Precision-recall", xlabel="Recall", ylabel="Precision")
    observed, predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    axes[2].plot(predicted, observed, "o-")
    axes[2].plot([0, 1], [0, 1], "--", color="grey")
    axes[2].set(title="Calibration", xlabel="Predicted probability", ylabel="Observed frequency")
    fig.tight_layout()
    fig.savefig(directory / "evaluation.png", dpi=150)
    plt.close(fig)


def train_task(
    task,
    trials=None,
    limit=None,
    root=ROOT,
    register=True,
    candidate=False,
    additional_training=None,
    promote_initial=True,
):
    params = parameters()
    df = dataset(task, root)
    if additional_training is not None:
        if not candidate:
            raise ValueError("Additional training data is allowed only in candidate retraining")
        additions = pd.read_parquet(additional_training)
        evidence = read_json(Path(additional_training).with_suffix(".evidence.json"))
        if (
            evidence["labels_mature_confirmed"] is not True
            or not (additions.split == "train").all()
        ):
            raise ValueError("Only admitted training rows with mature labels can be added")
        if set(additions.row_id) & set(df.row_id):
            raise ValueError("Additional rows overlap the frozen dataset")
        df = pd.concat([df, additions], ignore_index=True)
    features = task_features(task)
    if limit:
        df = pd.concat(
            [g.sample(min(len(g), limit), random_state=42) for _, g in df.groupby("split")]
        )
    df = df.sort_values(["approval_date", "row_id"] if task == "credit" else "row_id")
    train = df[df.split == "train"]
    val = df[df.split == "validation"]
    test = df[df.split == "test"]
    for split, group in [("train", train), ("validation", val), ("test", test)]:
        if set(group.target.unique()) != {0, 1}:
            raise ValueError(f"Both binary outcomes required in {task} {split}")
    x, y = train[features], train.target
    tuning_x, tuning_y = x, y
    cap = params["training"]["tuning_sample_limit"]
    if len(x) > cap:
        chosen, _ = train_test_split(np.arange(len(x)), train_size=cap, stratify=y, random_state=42)
        chosen = np.sort(chosen)
        tuning_x, tuning_y = x.iloc[chosen], y.iloc[chosen]
    trial_count = params["training"]["optuna_trials"] if trials is None else trials
    run_id = time.strftime("%Y%m%dT%H%M%S")
    directory = root / "artifacts" / MODEL_NAMES[task] / run_id
    directory.mkdir(parents=True, exist_ok=True)
    comparisons = {}
    candidates = {}
    for family in ["logistic", "forest", "xgboost"]:
        started = time.perf_counter()
        settings = tune(
            task,
            family,
            tuning_x,
            tuning_y,
            trial_count if family != "logistic" else min(trial_count, 3),
        )
        pipe = build_pipeline(task, family, settings, (len(y) - y.sum()) / max(1, y.sum()))
        calibrator = fit_calibration(pipe, task, x, y)
        raw = RiskModel(pipe, features, task)
        calibrated = RiskModel(pipe, features, task, calibrator)
        pv_raw = raw.predict_proba(val)[:, 1]
        pv_cal = calibrated.predict_proba(val)[:, 1]
        use_cal = brier_score_loss(val.target, pv_cal) < brier_score_loss(val.target, pv_raw)
        model, pv = (calibrated, pv_cal) if use_cal else (raw, pv_raw)
        threshold, cost = choose_threshold(
            val.target.to_numpy(),
            pv,
            params["decision"]["false_negative_cost"],
            params["decision"]["false_positive_cost"],
        )
        comparisons[family] = {
            "parameters": settings,
            "calibrated": bool(use_cal),
            "raw_validation_brier": float(brier_score_loss(val.target, pv_raw)),
            "calibrated_validation_brier": float(brier_score_loss(val.target, pv_cal)),
            "validation": metrics(val.target.to_numpy(), pv, threshold),
            "seconds": time.perf_counter() - started,
            "cost": cost,
        }
        candidates[family] = model
        print(
            f"{task} {family}: validation AP={comparisons[family]['validation']['pr_auc_average_precision']:.4f}",
            flush=True,
        )
    # Selection is locked before inspecting any test predictions.
    winner = sorted(
        comparisons,
        key=lambda f: (
            -comparisons[f]["validation"]["pr_auc_average_precision"],
            comparisons[f]["validation"]["brier"],
            comparisons[f]["cost"],
        ),
    )[0]
    model = candidates[winner]
    threshold = comparisons[winner]["validation"]["threshold"]
    save_json(directory / "selection.json", {"winner": winner, "comparisons": comparisons})
    if candidate:
        test_metrics = {
            "executed": False,
            "reason": "Final test sealed during controlled retraining",
        }
        p = None
    else:
        for family, fitted in candidates.items():
            comparisons[family]["test"] = metrics(
                test.target.to_numpy(),
                fitted.predict_proba(test)[:, 1],
                comparisons[family]["validation"]["threshold"],
            )
        p = model.predict_proba(test)[:, 1]
        test_metrics = metrics(
            test.target.to_numpy(), p, threshold, params["training"]["bootstrap_repeats"]
        )
    joblib.dump(model, directory / "model.joblib", compress=3)
    background = train[features].sample(min(64, len(train)), random_state=42)
    background.to_parquet(directory / "background.parquet", index=False)
    reference = train[features].sample(min(5000, len(train)), random_state=42)
    reference.to_parquet(directory / "reference.parquet", index=False)
    if p is not None:
        test[["row_id", "target"]].assign(probability=p).to_parquet(
            directory / "test_predictions.parquet", index=False
        )
    metadata = {
        "task": task,
        "model_name": MODEL_NAMES[task],
        "version": run_id,
        "winner": winner,
        "features": features,
        "schema_version": "1.0",
        "predicted_event": "loan_charge_off" if task == "credit" else "corporate_bankruptcy",
        "horizon": "historical_resolved_loan_outcome_unspecified" if task == "credit" else "1_year",
        "threshold": threshold,
        "calibrated": model.calibrator is not None,
        "validation": comparisons[winner]["validation"],
        "test": test_metrics,
        "comparisons": comparisons,
        "train_rows": len(train),
        "tuning_rows": len(tuning_x),
        "development_sample": bool(limit),
        "additional_training_sha256": source_fingerprint(additional_training)
        if additional_training
        else None,
        "optuna_trials": trial_count,
        "data_sha256": source_fingerprint(
            root / "data/processed" / ("sba.parquet" if task == "credit" else "polish.parquet")
        ),
        "test_ids_sha256": hashlib.sha256("\n".join(sorted(test.row_id)).encode()).hexdigest(),
        "qualification_ids_sha256": hashlib.sha256(
            "\n".join(sorted(val.row_id)).encode()
        ).hexdigest(),
        "model_sha256": source_fingerprint(directory / "model.joblib"),
        "warnings": (
            [
                "Historically approved and resolved loans only; censoring and selection bias.",
                "Not a one-year PD or validated pre-approval decision.",
            ]
            if task == "credit"
            else [
                "Historical Polish population; external validity not established.",
                "Bankruptcy probability is not credit PD.",
            ]
        ),
    }
    validation_prevalence = metadata["validation"]["prevalence"]
    if task == "bankruptcy_full":
        metadata["warnings"].append(
            "Temporalité exacte de l'agrégat Attr24 non certifiée ; absence de fuite temporelle résiduelle non garantie."
        )
    if metadata["validation"]["brier"] >= validation_prevalence * (1 - validation_prevalence):
        metadata["warnings"].append(
            "Validation Brier is worse than the prevalence-only baseline; probability accuracy is limited."
        )
    if p is not None:
        evaluation_plots(test.target, p, directory)
    else:
        evaluation_plots(val.target, model.predict_proba(val)[:, 1], directory)
    save_json(directory / "metadata.json", metadata)
    save_json(directory / "global_shap.json", global_explanation(model, background, directory))
    if register:
        from fintech_risk.registry import register_model

        register_model(directory, metadata, candidate=candidate or not promote_initial)
    if candidate:
        from fintech_risk.registry import append_event

        append_event(
            "candidate_trained",
            task,
            metadata.get("registry_version", run_id),
            "Revalidated data; champion unchanged; final test not rerun",
        )
    return directory, metadata


def explain(model, frame, background):
    import shap

    prep = model.pipeline.named_steps["preprocess"]
    estimator = model.pipeline.named_steps["estimator"]
    values = np.asarray(prep.transform(frame[model.features]), dtype=float)
    names = list(prep.get_feature_names_out())
    if isinstance(estimator, LogisticRegression):
        explanation = shap.LinearExplainer(
            estimator, np.asarray(prep.transform(background))
        ).shap_values(values)
        base = shap.LinearExplainer(
            estimator, np.asarray(prep.transform(background))
        ).expected_value
        scale = "base_model_log_odds"
    else:
        explainer = shap.TreeExplainer(estimator)
        explanation = explainer.shap_values(values)
        base = explainer.expected_value
        scale = (
            "base_model_probability"
            if isinstance(estimator, RandomForestClassifier)
            else "base_model_log_odds"
        )
    explanation = np.asarray(explanation)
    if explanation.ndim == 3:
        explanation = explanation[:, :, 1]
    base = float(np.asarray(base).flatten()[-1])
    return {
        "feature_names": names,
        "values": explanation.tolist(),
        "base_value": base,
        "transformed_inputs": values.tolist(),
        "scale": scale,
        "calibration_note": "SHAP explique le modèle de base ; la calibration transforme ensuite sa probabilité.",
        "interpretation": "Associations et contributions au modèle, sans interprétation causale.",
    }


def global_explanation(model, background, directory):
    result = explain(model, background, background)
    contributions = np.asarray(result["values"])
    result["mean_absolute_shap"] = dict(
        zip(result["feature_names"], np.mean(np.abs(contributions), axis=0).tolist(), strict=True)
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    shap.summary_plot(
        contributions,
        np.asarray(result["transformed_inputs"]),
        feature_names=result["feature_names"],
        show=False,
        max_display=15,
    )
    plt.tight_layout()
    plt.savefig(directory / "shap_summary.png", dpi=140, bbox_inches="tight")
    plt.close()
    return result


def compare_polish(root=ROOT):
    manifest = read_json(root / "artifacts/deployment.json")
    a = root / manifest["sme"]["path"]
    b = root / manifest["bankruptcy_full"]["path"]
    left, right = read_json(a / "metadata.json"), read_json(b / "metadata.json")
    if left["test_ids_sha256"] != right["test_ids_sha256"]:
        raise ValueError("Polish comparison requires identical held-out test IDs")
    save_json(
        root / "reports/generated/polish_comparison.json",
        {
            "same_test_ids": True,
            "simplified": left["test"],
            "full": right["test"],
            "warning": "Selection used validation only; this test comparison does not retune models.",
        },
    )
