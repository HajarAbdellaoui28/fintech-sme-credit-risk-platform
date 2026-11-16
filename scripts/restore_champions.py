"""Recover the initially approved local champions from immutable MLflow evaluations."""

import os
import shutil

import mlflow
from dotenv import load_dotenv

from fintech_risk.config import MODEL_NAMES, ROOT, read_json, save_json
from fintech_risk.data import source_fingerprint
from fintech_risk.registry import append_event

load_dotenv(ROOT / ".env")
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
client = mlflow.MlflowClient()
manifest = {}
for task, name in MODEL_NAMES.items():
    version = client.get_model_version(name, "1")
    temporary = ROOT / "tmp/recovery" / task
    temporary.mkdir(parents=True, exist_ok=True)
    recovered = client.download_artifacts(version.run_id, "evaluation", str(temporary))
    metadata = read_json(__import__("pathlib").Path(recovered) / "metadata.json")
    target = ROOT / "artifacts" / name / metadata["version"]
    if target.exists() and (target / "model.joblib").exists():
        if source_fingerprint(target / "model.joblib") != metadata["model_sha256"]:
            raise ValueError("Recovery destination contains a different artifact")
    shutil.copytree(recovered, target, dirs_exist_ok=True)
    assert source_fingerprint(target / "model.joblib") == metadata["model_sha256"]
    manifest[task] = {
        "path": target.relative_to(ROOT).as_posix(),
        "version": "1",
        "model_name": name,
        "model_sha256": metadata["model_sha256"],
    }
    client.set_registered_model_alias(name, "champion", "1")
    append_event(
        "recovery",
        task,
        "1",
        "Restored immutable MLflow evaluation after DVC output-isolation regression",
    )
save_json(ROOT / "artifacts/deployment.json", manifest)
print("Three original champion artifacts and aliases restored with verified digests.")
