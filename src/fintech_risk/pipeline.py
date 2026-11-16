"""DVC snapshots are disposable; approved serving artifacts never are DVC outputs."""

import os
import shutil

from fintech_risk.config import MODEL_NAMES, ROOT, read_json, save_json
from fintech_risk.models import train_task


def pipeline_train(tasks=None, trials=None, root=ROOT):
    manifest_path = root / "artifacts/deployment.json"
    before = read_json(manifest_path) if manifest_path.exists() else None
    import mlflow

    client = mlflow.MlflowClient(
        tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
    )
    aliases_before = {
        task: client.get_model_version_by_alias(ref["model_name"], "champion").version
        for task, ref in (before or {}).items()
    }
    output = root / "data/model-snapshots"
    output.mkdir(parents=True, exist_ok=True)
    snapshots = {}
    for task in tasks or MODEL_NAMES:
        if (output / task).exists():
            raise ValueError(
                "Snapshot target already exists; run through 'dvc repro -f train' to replace disposable snapshots safely"
            )
        directory, metadata = train_task(task, trials=trials, root=root, promote_initial=False)
        # Only this detached copy belongs to DVC. Registry/live paths are never removed.
        shutil.copytree(directory, output / task)
        snapshots[task] = {
            "model_name": metadata["model_name"],
            "registry_version": metadata["registry_version"],
            "model_sha256": metadata["model_sha256"],
            "live_path": directory.relative_to(root).as_posix(),
        }
    after = read_json(manifest_path) if manifest_path.exists() else None
    if before != after:
        raise RuntimeError("DVC training must never mutate the approved deployment manifest")
    aliases_after = {
        task: client.get_model_version_by_alias(ref["model_name"], "champion").version
        for task, ref in (before or {}).items()
    }
    if aliases_before != aliases_after:
        raise RuntimeError("DVC training must never mutate champion aliases")
    save_json(output / "snapshot_manifest.json", snapshots)
    return snapshots


def compare_snapshots(root=ROOT):
    a = read_json(root / "data/model-snapshots/sme/metadata.json")
    b = read_json(root / "data/model-snapshots/bankruptcy_full/metadata.json")
    if a["test_ids_sha256"] != b["test_ids_sha256"]:
        raise ValueError("Polish snapshots must share exactly the same held-out test")
    save_json(
        root / "reports/generated/polish_comparison.json",
        {
            "same_test_ids": True,
            "simplified": a["test"],
            "full": b["test"],
            "source": "DVC snapshots; these are candidates, not an implicit deployment",
            "warning": "No test-based tuning and no automatic champion promotion.",
        },
    )
