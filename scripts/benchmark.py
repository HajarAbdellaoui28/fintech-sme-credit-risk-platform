"""Measured latency: model-only and complete API, with explicit local conditions."""

import argparse
import concurrent.futures
import time

import httpx
import numpy as np

from fintech_risk.config import ROOT, save_json
from fintech_risk.schemas import CreditInput, FullPolishInput, SMEInput
from fintech_risk.service import ModelService

p = argparse.ArgumentParser()
p.add_argument("--requests", type=int, default=1000)
p.add_argument("--api", default="http://127.0.0.1:8000")
args = p.parse_args()
service = ModelService()
profiles = __import__("json").loads((ROOT / "artifacts/demo_profiles.json").read_text())
payloads = {
    "sme": {
        "sme_id": "BENCHMARK",
        "sector": "Services",
        "annual_revenue": 4500000.0,
        "debt_ratio": 0.42,
        "current_ratio": 1.85,
        "requested_amount": 500000.0,
        "loan_term_months": 36,
        "past_defaults": 0,
    },
    "bankruptcy_full": {"features": profiles[0]["features"]},
    "credit": {
        "GrAppv": 100000.0,
        "SBA_Appv": 75000.0,
        "NoEmp": 10.0,
        "NAICS2": "54",
        "NewExist": "1",
        "State": "CA",
        "UrbanRural": "1",
        "LowDoc": "N",
        "RevLineCr": "N",
    },
}
contracts = {"sme": SMEInput, "bankruptcy_full": FullPolishInput, "credit": CreditInput}
routes = {
    "sme": "/predict/sme",
    "bankruptcy_full": "/predict/bankruptcy/full",
    "credit": "/predict/credit",
}


def summarize(times):
    return {
        "requests": len(times),
        "p50_ms": float(np.quantile(times, 0.5)),
        "p95_ms": float(np.quantile(times, 0.95)),
        "p99_ms": float(np.quantile(times, 0.99)),
        "target_p95_below_100ms": bool(np.quantile(times, 0.95) < 100),
    }


report = {
    "completed": False,
    "conditions": {
        "transport": "HTTP keep-alive, local loopback",
        "warmup": 20,
        "note": "SME includes cached two-feature SHAP. Other prediction routes exclude SHAP. No cold-start latency claim.",
        "concurrency": [1, 4],
        "requests_per_case": args.requests,
        "inference_threads_per_estimator": 1,
    },
    "tasks": {},
}
with httpx.Client(timeout=60) as client:
    for task, payload in payloads.items():
        bundle = service.get(task)
        frame = service.frame(task, contracts[task].model_validate(payload))
        for _ in range(20):
            bundle["model"].predict_proba(frame)
        timings = []
        for _ in range(args.requests):
            started = time.perf_counter()
            bundle["model"].predict_proba(frame)
            timings.append((time.perf_counter() - started) * 1000)
        entry = {"model_only": summarize(timings), "api": {}}
        for workers in [1, 4]:
            for _ in range(20):
                client.post(args.api + routes[task], json=payload).raise_for_status()

            def one(_, target=routes[task], body=payload):
                started = time.perf_counter()
                response = client.post(args.api + target, json=body)
                return (time.perf_counter() - started) * 1000, response.status_code

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(one, range(args.requests)))
            entry["api"][str(workers)] = {
                **summarize([r[0] for r in results]),
                "error_count": sum(r[1] != 200 for r in results),
            }
        report["tasks"][task] = entry
        save_json(ROOT / "reports/generated/latency.json", report)
        print(task, entry, flush=True)
report["completed"] = True
save_json(ROOT / "reports/generated/latency.json", report)
