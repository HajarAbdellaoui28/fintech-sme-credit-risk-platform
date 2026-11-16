"""Input drift only. A report never promotes a model or asserts performance degradation."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance

from fintech_risk.config import ROOT, parameters, read_json, save_json
from fintech_risk.features import CREDIT_CATEGORICAL


def feature_drift(reference, current, settings):
    results = {}
    for column in reference.columns:
        a, b = reference[column].dropna(), current[column].dropna()
        if len(a) == 0 or len(b) == 0:
            results[column] = {
                "score": None,
                "drifted": True,
                "reason": "Empty observed distribution",
            }
        elif column in CREDIT_CATEGORICAL:
            keys = sorted(set(a.astype(str)) | set(b.astype(str)))
            pa = a.astype(str).value_counts(normalize=True).reindex(keys, fill_value=0).to_numpy()
            pb = b.astype(str).value_counts(normalize=True).reindex(keys, fill_value=0).to_numpy()
            score = float(jensenshannon(pa, pb))
            results[column] = {
                "score": score,
                "method": "jensenshannon",
                "drifted": score >= settings["categorical_threshold"],
            }
        else:
            scale = float(np.std(a))
            score = (
                float(wasserstein_distance(a, b) / scale)
                if scale > 0
                else (0.0 if np.array_equal(a.unique(), b.unique()) else 1.0)
            )
            results[column] = {
                "score": score,
                "method": "normalized_wasserstein",
                "drifted": score >= settings["numeric_threshold"],
            }
        results[column]["reference_missing_share"] = float(reference[column].isna().mean())
        results[column]["current_missing_share"] = float(current[column].isna().mean())
    return results


def drift_report(task, current_path):
    from evidently import DataDefinition, Dataset, Report
    from evidently.presets import DataDriftPreset

    manifest = read_json(ROOT / "artifacts/deployment.json")
    directory = ROOT / manifest[task]["path"]
    reference = pd.read_parquet(directory / "reference.parquet")
    path = current_path
    current = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    features = list(reference.columns)
    if set(current.columns) != set(features):
        raise ValueError("Current drift dataset must contain exactly the model input columns")
    current = current[features]
    numeric = [f for f in features if f not in CREDIT_CATEGORICAL]
    for f in numeric:
        current[f] = pd.to_numeric(current[f], errors="raise")
        if not np.isfinite(current[f].dropna().to_numpy()).all():
            raise ValueError(f"Non-finite drift input: {f}")
    settings = parameters()["drift"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    base = ROOT / "reports/generated/drift" / f"{task}-{stamp}"
    base.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "task": task,
        "model_version": manifest[task]["version"],
        "at": stamp,
        "reference_rows": len(reference),
        "current_rows": len(current),
        "performance_degradation": "unknown_without_observed_labels",
        "automatic_promotion": False,
    }
    if len(current) < settings["minimum_rows"]:
        result.update(
            {
                "status": "insufficient_data",
                "recommendation": "Collect at least 200 rows before interpreting drift.",
            }
        )
    else:
        definition = DataDefinition(
            numerical_columns=numeric,
            categorical_columns=[c for c in features if c in CREDIT_CATEGORICAL],
        )
        report = Report(
            [
                DataDriftPreset(
                    drift_share=settings["drift_share"],
                    num_method=settings["numeric_method"],
                    num_threshold=settings["numeric_threshold"],
                    cat_method=settings["categorical_method"],
                    cat_threshold=settings["categorical_threshold"],
                )
            ]
        )
        snapshot = report.run(
            reference_data=Dataset.from_pandas(reference, data_definition=definition),
            current_data=Dataset.from_pandas(current, data_definition=definition),
        )
        snapshot.save_html(str(base) + ".html")
        snapshot.save_json(str(base) + ".evidently.json")
        checks = feature_drift(reference, current, settings)
        fraction = sum(v["drifted"] for v in checks.values()) / len(checks)
        result.update(
            {
                "status": "drift_detected"
                if fraction >= settings["drift_share"]
                else "no_drift_detected",
                "drift_share": fraction,
                "features": checks,
                "recommendation": "Investigate inputs and consider controlled retraining; await mature labels."
                if fraction >= settings["drift_share"]
                else "Continue collecting representative observations.",
                "evidently_html": base.name + ".html",
            }
        )
    save_json(str(base) + ".json", result)
    return result
