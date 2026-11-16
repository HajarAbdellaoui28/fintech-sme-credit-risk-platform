"""Demonstrate Evidently on unchanged and deliberately perturbed inputs, never training data."""

import pandas as pd

from fintech_risk.config import ROOT, read_json, save_json
from fintech_risk.features import CREDIT_CATEGORICAL
from fintech_risk.monitoring import drift_report

manifest = read_json(ROOT / "artifacts/deployment.json")
directory = ROOT / "tmp/drift-probes"
directory.mkdir(parents=True, exist_ok=True)
results = []
for task, model in manifest.items():
    reference = pd.read_parquet(ROOT / model["path"] / "reference.parquet")
    unchanged = directory / f"{task}-unchanged.parquet"
    reference.to_parquet(unchanged, index=False)
    control = drift_report(task, unchanged)
    assert control["status"] == "no_drift_detected", control
    changed = reference.copy()
    for column in changed:
        if column in CREDIT_CATEGORICAL:
            changed[column] = "UNKNOWN"
        else:
            scale = float(changed[column].std())
            changed[column] += 2 * scale if scale > 0 else 1
    probe = directory / f"{task}-perturbed.parquet"
    changed.to_parquet(probe, index=False)
    shifted = drift_report(task, probe)
    assert shifted["status"] == "drift_detected", shifted
    assert not shifted["automatic_promotion"]
    results.append(
        {
            "task": task,
            "control_status": control["status"],
            "perturbed_status": shifted["status"],
            "drift_share": shifted["drift_share"],
        }
    )
save_json(
    ROOT / "reports/generated/drift_verification.json",
    {
        "executed": True,
        "probe_type": "deliberate perturbation only, no production drift claim",
        "results": results,
        "champions_unchanged": manifest == read_json(ROOT / "artifacts/deployment.json"),
    },
)
print("Evidently control and perturbation verified for all three models.")
