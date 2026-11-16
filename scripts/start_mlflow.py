"""Run MLflow locally against the same PostgreSQL and artifact proxy as Compose."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env")
os.environ.setdefault("MLFLOW_SERVER_ENABLE_JOB_EXECUTION", "false")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
password = os.environ["POSTGRES_PASSWORD"]
args = [
    str(root / ".venv/Scripts/mlflow.exe"),
    "server",
    "--backend-store-uri",
    f"postgresql+psycopg://fintech:{password}@127.0.0.1:5433/mlflow",
    "--artifacts-destination",
    str(root / "artifacts/mlflow"),
    "--serve-artifacts",
    "--host",
    "127.0.0.1",
    "--port",
    "5001",
    "--workers",
    "1",
]
sys.exit(subprocess.call(args, cwd=root))
