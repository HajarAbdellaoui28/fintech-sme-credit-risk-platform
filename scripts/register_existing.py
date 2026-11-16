"""Retry registration of completed artifacts without retraining or reopening the test set."""

import argparse
import os
import sys
import time

import httpx
from dotenv import load_dotenv

from fintech_risk.config import MODEL_NAMES, ROOT, read_json
from fintech_risk.registry import register_model

load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "60")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "0")
parser = argparse.ArgumentParser()
parser.add_argument("--task", choices=["all", *MODEL_NAMES], default="all")
args = parser.parse_args()
uri = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
for _attempt in range(30):
    try:
        if httpx.get(uri + "/health", timeout=2).status_code == 200:
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise RuntimeError("MLflow is not ready; no artifact or champion was changed")
tasks = MODEL_NAMES if args.task == "all" else [args.task]
for task in tasks:
    paths = sorted((ROOT / "artifacts" / MODEL_NAMES[task]).glob("*/metadata.json"))
    if not paths:
        raise ValueError(f"No completed training for {task}")
    path = paths[-1]
    metadata = read_json(path)
    if "registry_version" in metadata:
        print(task, "already registered", metadata["registry_version"], flush=True)
        continue
    print("Registering", task, flush=True)
    print("Registered", task, register_model(path.parent, metadata), flush=True)
