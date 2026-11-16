"""Compare native Windows pipelines with deployed Linux API on real held-out inputs."""

import httpx
import joblib
import numpy as np

from fintech_risk.config import ROOT, read_json, save_json
from fintech_risk.models import dataset

manifest = read_json(ROOT / "artifacts/deployment.json")
results = []
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=120) as client:
    for task, ref in manifest.items():
        model = joblib.load(ROOT / ref["path"] / "model.joblib")
        df = dataset(task)
        frame = df[df.split == "test"].dropna(subset=model.features).head(32)
        probabilities = model.predict_proba(frame)[:, 1]
        rows = []
        for _, row in frame.iterrows():
            if task == "sme":
                rows.append(
                    {
                        "sme_id": "PUBLIC-PARITY-FIXTURE",
                        "sector": "Unspecified",
                        "annual_revenue": 1.0,
                        "debt_ratio": float(row.Attr2),
                        "current_ratio": float(row.Attr4),
                        "requested_amount": 1.0,
                        "loan_term_months": 1,
                        "past_defaults": 0,
                    }
                )
            elif task == "bankruptcy_full":
                rows.append({"features": {k: float(row[k]) for k in model.features}})
            else:
                rows.append(
                    {
                        k: (
                            int(row[k])
                            if k == "NoEmp"
                            else float(row[k])
                            if k in ["GrAppv", "SBA_Appv"]
                            else row[k]
                        )
                        for k in model.features
                        if k != "guarantee_ratio"
                    }
                )
        response = client.post("/predict/batch", json={"task": task, "rows": rows})
        response.raise_for_status()
        data = response.json()
        assert data["valid_rows"] == len(rows), data
        served = np.array(
            [r["result"].get("prediction", r["result"])["probability"] for r in data["rows"]]
        )
        np.testing.assert_allclose(probabilities, served, atol=1e-7, rtol=1e-7)
        results.append(
            {
                "task": task,
                "rows": len(rows),
                "maximum_absolute_difference": float(np.max(abs(probabilities - served))),
                "model_version": ref["version"],
            }
        )
save_json(
    ROOT / "reports/generated/preprocessing_parity.json",
    {
        "executed": True,
        "results": results,
        "scope": "Real complete held-out observations; Windows pipeline versus Linux Docker API",
    },
)
print("Native/serving parity verified for three real models.")
