"""Explicit admission of observed, mature labels before controlled retraining."""

import pandas as pd

from fintech_risk.config import ROOT, read_json, save_json
from fintech_risk.data import source_fingerprint, validate_prepared
from fintech_risk.features import CREDIT_FEATURES, POLISH_FEATURES
from fintech_risk.models import dataset


def admit(task, data_path, evidence_path):
    evidence = read_json(evidence_path)
    required = {
        "source",
        "observed_at",
        "label_policy",
        "horizon",
        "labels_mature_confirmed",
        "source_sha256",
    }
    if required - evidence.keys() or evidence["labels_mature_confirmed"] is not True:
        raise ValueError(
            "Documented source, observation date, horizon and confirmed mature labels required"
        )
    if source_fingerprint(data_path) != evidence["source_sha256"]:
        raise ValueError("Label evidence does not match supplied data digest")
    expected_horizon = (
        "historical_resolved_loan_outcome_unspecified" if task == "credit" else "1_year"
    )
    if evidence["horizon"] != expected_horizon:
        raise ValueError("Label horizon does not match this model")
    features = CREDIT_FEATURES if task == "credit" else POLISH_FEATURES
    current = dataset(task)
    new = pd.read_parquet(data_path) if data_path.suffix == ".parquet" else pd.read_csv(data_path)
    if set(features + ["target", "row_id"]) - set(new):
        raise ValueError("Required features, binary target and stable row_id are missing")
    if not new.target.isin([0, 1]).all() or new.row_id.astype(str).isin(current.row_id).any():
        raise ValueError("Labels must be binary and row IDs must not overlap the frozen dataset")
    new["row_id"] = new.row_id.astype(str)
    new["target"] = new.target.astype("int64")
    new["split"] = "train"
    validate_prepared(new, features)
    if task == "credit":
        if "approval_date" not in new:
            raise ValueError("Chronological retraining requires approval_date")
        new["approval_date"] = pd.to_datetime(new.approval_date, errors="raise")
        boundary = pd.to_datetime(current[current.split == "validation"].approval_date).min()
        if (new.approval_date >= boundary).any():
            raise ValueError(
                "Newer SBA data requires a new prospectively defined qualification protocol; cannot train on the future and qualify on the past"
            )
    numeric = [
        c
        for c in features
        if c not in {"NAICS2", "NewExist", "State", "UrbanRural", "LowDoc", "RevLineCr"}
    ]
    import numpy as np

    if not np.isfinite(new[numeric].to_numpy(dtype=float)).all():
        raise ValueError("New training observations must have finite documented features")
    path = ROOT / "data/interim/admitted" / f"{task}-{evidence['source_sha256'][:16]}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    new.to_parquet(path, index=False)
    save_json(path.with_suffix(".evidence.json"), evidence)
    return path
