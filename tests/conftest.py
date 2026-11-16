"""Small synthetic fixtures train real estimators; never used as production evidence."""

import hashlib

import joblib
import pandas as pd
import pytest
from sklearn.datasets import make_classification

from fintech_risk.config import MODEL_NAMES, save_json
from fintech_risk.features import POLISH_FEATURES
from fintech_risk.models import RiskModel, build_pipeline, metrics, task_features


@pytest.fixture(scope="session")
def fixture_data():
    x, y = make_classification(
        n_samples=160, n_features=64, n_informative=8, weights=[0.8, 0.2], random_state=42
    )
    frame = pd.DataFrame(x, columns=POLISH_FEATURES)
    frame["Attr2"] = frame.Attr2.abs()
    frame["Attr4"] = frame.Attr4.abs()
    return frame, y


@pytest.fixture()
def client(tmp_path, monkeypatch, fixture_data):
    from fastapi.testclient import TestClient

    import fintech_risk.service as service_module
    from fintech_risk.api import app
    from fintech_risk.database import Base, engine

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'tests.db').as_posix()}")
    monkeypatch.setenv("ADMIN_TOKEN", "unit-test-only-secret")
    monkeypatch.setattr(service_module, "ROOT", tmp_path)
    Base.metadata.create_all(engine())
    frame, y = fixture_data
    manifest = {}
    for task in MODEL_NAMES:
        data = frame.copy()
        if task == "credit":
            data = pd.DataFrame(
                {
                    "GrAppv": frame.Attr2 * 100000 + 200,
                    "SBA_Appv": frame.Attr2 * 75000 + 100,
                    "guarantee_ratio": 0.75,
                    "NoEmp": frame.Attr4 * 10,
                    "NAICS2": "54",
                    "NewExist": "1",
                    "State": "CA",
                    "UrbanRural": "1",
                    "LowDoc": "N",
                    "RevLineCr": "N",
                }
            )
        features = task_features(task)
        pipe = build_pipeline(task, "logistic").fit(data[features], y)
        model = RiskModel(pipe, features, task)
        path = tmp_path / "artifacts" / task
        path.mkdir(parents=True)
        joblib.dump(model, path / "model.joblib")
        data[features].head(20).to_parquet(path / "background.parquet", index=False)
        metric = metrics(y, model.predict_proba(data)[:, 1], 0.1)
        save_json(
            path / "metadata.json",
            {
                "features": features,
                "model_name": MODEL_NAMES[task],
                "horizon": "historical_resolved_loan_outcome_unspecified"
                if task == "credit"
                else "1_year",
                "predicted_event": "loan_charge_off"
                if task == "credit"
                else "corporate_bankruptcy",
                "schema_version": "1.0",
                "threshold": 0.1,
                "warnings": ["SYNTHETIC TEST FIXTURE"],
                "winner": "logistic",
                "calibrated": False,
                "validation": metric,
                "test": metric,
            },
        )
        manifest[task] = {
            "path": f"artifacts/{task}",
            "version": "test-fixture",
            "model_sha256": hashlib.sha256((path / "model.joblib").read_bytes()).hexdigest(),
        }
    save_json(tmp_path / "artifacts/deployment.json", manifest)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sme():
    return {
        "sme_id": "PME-8842",
        "sector": "Services",
        "annual_revenue": 4500000.0,
        "debt_ratio": 0.42,
        "current_ratio": 1.85,
        "requested_amount": 500000.0,
        "loan_term_months": 36,
        "past_defaults": 0,
    }


@pytest.fixture()
def credit():
    return {
        "GrAppv": 100000.0,
        "SBA_Appv": 75000.0,
        "NoEmp": 10.0,
        "NAICS2": "54",
        "NewExist": "1",
        "State": "CA",
        "UrbanRural": "1",
        "LowDoc": "N",
        "RevLineCr": "N",
    }
