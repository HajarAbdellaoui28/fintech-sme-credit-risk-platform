"""Execute protected local candidate promotion and rollback with final-test seal checks."""

import os

import httpx
from dotenv import load_dotenv

from fintech_risk.config import ROOT, read_json, save_json

load_dotenv(ROOT / ".env")
before = read_json(ROOT / "artifacts/deployment.json")
paths = sorted((ROOT / "artifacts/polish_bankruptcy_simplified_1y").glob("*/metadata.json"))
sealed = [
    (path, read_json(path))
    for path in paths
    if read_json(path).get("test", {}).get("executed") is False
]
if not sealed:
    raise RuntimeError(
        "A completed controlled-retraining candidate with a sealed final test is required"
    )
candidate_path, candidate = sealed[-1]
assert candidate["registry_version"] != before["sme"]["version"]
assert candidate["test"]["executed"] is False
assert not (candidate_path.parent / "test_predictions.parquet").exists()
payload = {
    "task": "sme",
    "candidate_path": candidate_path.parent.relative_to(ROOT).as_posix(),
    "reason": "Vérification locale autorisée : candidat reproductible, puis rollback immédiat",
}
headers = {"X-Admin-Token": os.environ["ADMIN_TOKEN"]}
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=90) as client:
    unauthorized = client.post("/management/promote", json=payload)
    assert unauthorized.status_code == 403
    promotion = client.post("/management/promote", json=payload, headers=headers)
    assert promotion.status_code == 200, promotion.text
    assert (
        client.get("/model-info").json()["models"]["sme"]["version"]
        == candidate["registry_version"]
    )
    rollback = client.post(
        "/management/rollback", json={"task": "sme", "reason": payload["reason"]}, headers=headers
    )
    assert rollback.status_code == 200, rollback.text
    assert client.get("/model-info").json()["models"]["sme"]["version"] == before["sme"]["version"]
after = read_json(ROOT / "artifacts/deployment.json")
assert before == after
save_json(
    ROOT / "reports/generated/model_delivery_verification.json",
    {
        "executed": True,
        "candidate_version": candidate["registry_version"],
        "unauthorized_promotion_status": unauthorized.status_code,
        "promotion_status": promotion.status_code,
        "rollback_status": rollback.status_code,
        "original_champions_restored": True,
        "candidate_final_test_executed": False,
    },
)
print("Authorized candidate promotion and rollback verified; original champions restored.")
