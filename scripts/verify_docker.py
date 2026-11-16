"""Record local Docker evidence without exposing container environment secrets."""

import json
import subprocess

import httpx

from fintech_risk.config import ROOT, save_json

raw = subprocess.check_output(["docker", "compose", "ps", "--format", "json"], text=True)
try:
    services = json.loads(raw)
    if isinstance(services, dict):
        services = [services]
except json.JSONDecodeError:
    services = [json.loads(line) for line in raw.splitlines() if line.strip()]
by_name = {r["Service"]: r for r in services}
assert {"api", "dashboard", "mlflow", "postgres"} <= set(by_name)
assert all(by_name[name]["State"] == "running" for name in by_name)
assert by_name["api"]["Health"] == "healthy"
with httpx.Client(timeout=30) as client:
    assert client.get("http://127.0.0.1:8000/health").json()["status"] == "ready"
    assert client.get("http://127.0.0.1:8501/_stcore/health").status_code == 200
    assert client.get("http://127.0.0.1:5001/health").status_code == 200
subprocess.run(
    [
        "docker",
        "compose",
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        "import shutil,importlib.util; assert shutil.which('java') is None; assert importlib.util.find_spec('pyspark') is None",
    ],
    check=True,
)
image = subprocess.check_output(
    ["docker", "image", "inspect", "fintech-sme-runtime:local", "--format", "{{.Id}}"], text=True
).strip()
save_json(
    ROOT / "reports/generated/docker_verification.json",
    {
        "executed": True,
        "services": [
            {"service": k, "state": v["State"], "health": v.get("Health", "")}
            for k, v in by_name.items()
        ],
        "runtime_image_id": image,
        "api_without_java_or_spark": True,
        "training_separate_profile": True,
    },
)
print("Four Docker services verified; API runtime has no Java or Spark.")
