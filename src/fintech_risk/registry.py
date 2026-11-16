"""Independent MLflow registration and explicit, audited local promotion."""

import os
import secrets
import sys
import threading
from datetime import datetime, timezone

from fintech_risk.config import ROOT, parameters, read_json, save_json

_LOCK = threading.RLock()


def register_model(directory, metadata, candidate=False):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import joblib
    import mlflow
    import pandas as pd
    from mlflow.models import infer_signature
    from mlflow.tracking import MlflowClient

    class PortableRisk(mlflow.pyfunc.PythonModel):
        def load_context(self, context):
            self.bundle = joblib.load(context.artifacts["bundle"])

        def predict(self, context, model_input, params=None):
            return pd.DataFrame({"probability": self.bundle.predict_proba(model_input)[:, 1]})

    uri = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(metadata["model_name"])
    model = joblib.load(directory / "model.joblib")
    example = pd.read_parquet(directory / "background.parquet").head(2)
    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "task": metadata["task"],
                "winner": metadata["winner"],
                "calibrated": metadata["calibrated"],
                "seed": 42,
                "train_rows": metadata["train_rows"],
                "development_sample": metadata["development_sample"],
                "data_sha256": metadata["data_sha256"],
            }
        )
        for split in ["validation", "test"]:
            mlflow.log_metrics(
                {
                    f"{split}_{k}": v
                    for k, v in metadata[split].items()
                    if isinstance(v, (int, float))
                }
            )
        signature = infer_signature(
            example, pd.DataFrame({"probability": model.predict_proba(example)[:, 1]})
        )
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=PortableRisk(),
            artifacts={"bundle": str((directory / "model.joblib").resolve())},
            signature=signature,
            input_example=example,
            code_paths=[str(ROOT / "src/fintech_risk")],
            pip_requirements=[
                "scikit-learn==1.7.2",
                "numpy==1.26.4",
                "pandas==2.3.3",
                "scipy==1.17.1",
                "xgboost-cpu==3.0.5; sys_platform == 'linux'",
                "xgboost==3.0.5; sys_platform != 'linux'",
                "optuna==4.9.0",
                "joblib==1.6.0",
                "pyarrow==23.0.1",
                "pandera[pandas]==0.27.1",
                "pyyaml==6.0.3",
            ],
            registered_model_name=metadata["model_name"],
        )
        metadata["mlflow_run_id"] = run.info.run_id
        metadata["mlflow_model_uri"] = info.model_uri
        metadata["registry_version"] = str(info.registered_model_version)
        save_json(directory / "metadata.json", metadata)
        mlflow.log_artifacts(str(directory), artifact_path="evaluation")
    client = MlflowClient()
    version = metadata["registry_version"]
    client.set_registered_model_alias(metadata["model_name"], "candidate", version)
    deployment = ROOT / "artifacts/deployment.json"
    manifest = read_json(deployment) if deployment.exists() else {}
    if not candidate and metadata["task"] not in manifest:
        if metadata["development_sample"]:
            raise ValueError("Development samples cannot become initial champions")
        client.set_registered_model_alias(metadata["model_name"], "champion", version)
        manifest[metadata["task"]] = entry(directory, metadata)
        save_json(deployment, manifest)
        append_event(
            "initial_promotion", metadata["task"], version, "initial architecture approval"
        )
    return version


def entry(directory, metadata):
    return {
        "path": directory.relative_to(ROOT).as_posix(),
        "version": metadata.get("registry_version", metadata["version"]),
        "model_sha256": metadata["model_sha256"],
        "model_name": metadata["model_name"],
    }


def append_event(action, task, version, reason):
    path = ROOT / "artifacts/management_events.json"
    events = read_json(path) if path.exists() else []
    events.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "task": task,
            "version": str(version),
            "reason": reason,
        }
    )
    save_json(path, events)


def check_promotion(candidate, champion):
    policy = parameters()["promotion"]
    if candidate["development_sample"]:
        return False, ["Development sample is not eligible for promotion"]
    if candidate["features"] != champion["features"] or candidate["horizon"] != champion["horizon"]:
        return False, ["Feature or horizon mismatch"]
    # Qualification is validation, never repeated selection on the final test.
    c, old = candidate["validation"], champion["validation"]
    failures = []
    if candidate.get("qualification_ids_sha256") != champion.get("qualification_ids_sha256"):
        failures.append(
            "Qualification data changed; a separately approved qualification protocol is required"
        )
    if c["pr_auc_average_precision"] < old["pr_auc_average_precision"] - policy["maximum_ap_drop"]:
        failures.append("Average precision regression")
    if c["brier"] > old["brier"] + policy["maximum_brier_increase"]:
        failures.append("Calibration regression")
    if c["simulated_cost"] > old["simulated_cost"] + policy["maximum_cost_increase"]:
        failures.append("Cost regression")
    return not failures, failures


def promote(task, directory, token, reason):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise PermissionError("Administrator authorization required")
    directory = directory.resolve()
    if not directory.is_relative_to((ROOT / "artifacts").resolve()):
        raise ValueError("Candidate must belong to the local artifact store")
    metadata = read_json(directory / "metadata.json")
    from fintech_risk.data import source_fingerprint

    if source_fingerprint(directory / "model.joblib") != metadata["model_sha256"]:
        raise ValueError("Candidate artifact digest mismatch")
    if metadata["task"] != task or "registry_version" not in metadata:
        raise ValueError("Candidate task or registration mismatch")
    with _LOCK:
        manifest = read_json(ROOT / "artifacts/deployment.json")
        champion = read_json(ROOT / manifest[task]["path"] / "metadata.json")
        allowed, failures = check_promotion(metadata, champion)
        if not allowed:
            raise ValueError("; ".join(failures))
        import mlflow

        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"))
        client = mlflow.MlflowClient()
        version = metadata["registry_version"]
        client.set_registered_model_alias(metadata["model_name"], "champion", version)
        old = manifest[task]
        manifest[task] = {**entry(directory, metadata), "previous": old}
        save_json(ROOT / "artifacts/deployment.json", manifest)
        append_event("promotion", task, version, reason)
    return manifest[task]


def rollback(task, token, reason):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise PermissionError("Administrator authorization required")
    with _LOCK:
        manifest = read_json(ROOT / "artifacts/deployment.json")
        previous = manifest[task].get("previous")
        if not previous:
            raise ValueError("No previous champion")
        import mlflow

        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"))
        mlflow.MlflowClient().set_registered_model_alias(
            previous["model_name"], "champion", previous["version"]
        )
        manifest[task] = previous
        save_json(ROOT / "artifacts/deployment.json", manifest)
        append_event("rollback", task, previous["version"], reason)
    return previous
