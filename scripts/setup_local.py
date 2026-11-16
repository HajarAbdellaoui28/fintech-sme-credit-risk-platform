"""Create local-only secrets without displaying them or touching existing configuration."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if not path.exists():
    password = secrets.token_hex(20)
    path.write_text(
        f"POSTGRES_PASSWORD={password}\nADMIN_TOKEN={secrets.token_urlsafe(40)}\n"
        f"DATABASE_URL=postgresql+psycopg://fintech:{password}@127.0.0.1:5433/fintech\n"
        "MLFLOW_TRACKING_URI=http://127.0.0.1:5001\nAPI_URL=http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
for directory in ["artifacts", "storage", "reports/generated", "data/processed", "configs"]:
    (root / directory).mkdir(parents=True, exist_ok=True)
print("Local configuration ready; secrets were not printed.")
