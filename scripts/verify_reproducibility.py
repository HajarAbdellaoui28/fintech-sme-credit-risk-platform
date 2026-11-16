"""Check snapshot metrics, protected deployment and immutable raw provenance after DVC."""

import os

import mlflow
from dotenv import load_dotenv

from fintech_risk.config import ROOT, read_json, save_json
from fintech_risk.data import source_fingerprint

load_dotenv(ROOT / ".env")
baseline = read_json(ROOT / "reports/generated/repro_baseline.json")
manifest = read_json(ROOT / "artifacts/deployment.json")
assert baseline["manifest"] == manifest
client = mlflow.MlflowClient(tracking_uri=os.environ["MLFLOW_TRACKING_URI"])
aliases = {
    task: client.get_model_version_by_alias(ref["model_name"], "champion").version
    for task, ref in manifest.items()
}
assert aliases == baseline["champion_aliases"]
results = []
for task, ref in manifest.items():
    original = read_json(ROOT / ref["path"] / "metadata.json")
    fresh = read_json(ROOT / "data/model-snapshots" / task / "metadata.json")
    assert fresh["test_ids_sha256"] == original["test_ids_sha256"]
    differences = {
        key: abs(fresh["test"][key] - original["test"][key])
        for key in [
            "roc_auc",
            "pr_auc_average_precision",
            "precision",
            "recall",
            "f1",
            "brier",
            "threshold",
        ]
    }
    assert max(differences.values()) < 1e-10, differences
    assert source_fingerprint(ROOT / ref["path"] / "model.joblib") == ref["model_sha256"]
    results.append(
        {
            "task": task,
            "fresh_registry_version": fresh["registry_version"],
            "champion_version_unchanged": ref["version"],
            "maximum_metric_difference": max(differences.values()),
        }
    )
audit = read_json(ROOT / "reports/generated/data_audit.json")
for path, record in audit["files"].items():
    assert source_fingerprint(ROOT / path) == record["sha256"]
save_json(
    ROOT / "reports/generated/reproducibility.json",
    {
        "executed": True,
        "stages": ["prepare", "train", "compare"],
        "results": results,
        "raw_data_unchanged": True,
        "deployment_manifest_unchanged": True,
        "champion_aliases_unchanged": True,
        "note": "Frozen pipeline repeated for reproducibility; no test-driven retuning or automatic promotion.",
    },
)
print("DVC reproduction, identical metrics and protected champions verified.")
