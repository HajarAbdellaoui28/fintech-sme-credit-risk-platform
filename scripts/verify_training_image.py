"""Execute Java/Spark in the optional training image, isolated from inference."""

import json
import subprocess

from fintech_risk.config import ROOT, save_json

code = """
import json, platform, subprocess
import pyspark
from fintech_risk.data import spark_session
spark = spark_session()
assert spark.version == pyspark.__version__ == '3.5.8'
assert spark.range(17).count() == 17
print('TRAINING_EVIDENCE=' + json.dumps({
    'python': platform.python_version(),
    'spark_jvm': spark.version,
    'pyspark': pyspark.__version__,
    'java': subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True).splitlines()[0],
    'real_spark_row_count': 17,
}))
spark.stop()
"""
result = subprocess.run(
    [
        "docker",
        "compose",
        "--profile",
        "training",
        "run",
        "--rm",
        "--no-deps",
        "training",
        "python",
        "-c",
        code,
    ],
    check=False,
    capture_output=True,
    text=True,
    timeout=180,
)
if result.returncode:
    raise RuntimeError(result.stderr[-6000:] + result.stdout[-2000:])
line = next(line for line in result.stdout.splitlines() if line.startswith("TRAINING_EVIDENCE="))
evidence = json.loads(line.split("=", 1)[1])
evidence["executed"] = True
evidence["scope"] = "Real Spark smoke test; complete training replay executed natively, separately."
evidence["image_id"] = subprocess.check_output(
    ["docker", "image", "inspect", "fintech-sme-training:local", "--format", "{{.Id}}"],
    text=True,
).strip()
save_json(ROOT / "reports/generated/training_image_verification.json", evidence)
print(json.dumps(evidence))
