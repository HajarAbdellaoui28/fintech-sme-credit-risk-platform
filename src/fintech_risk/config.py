"""Configuration shared by offline pipelines and online services."""

import json
import os
import tempfile
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("FINTECH_ROOT", Path(__file__).resolve().parents[2])).resolve()
MODEL_NAMES = {
    "sme": "polish_bankruptcy_simplified_1y",
    "bankruptcy_full": "polish_bankruptcy_full_1y",
    "credit": "sba_credit_chargeoff",
}


def parameters():
    return yaml.safe_load((ROOT / "params.yaml").read_text(encoding="utf-8"))


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=path.name, suffix=".tmp", delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
