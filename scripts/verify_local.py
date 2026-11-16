"""Live integration checks against real deployed models and PostgreSQL."""

import argparse
import json

import httpx

from fintech_risk.config import ROOT, save_json

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://127.0.0.1:8000")
args = p.parse_args()
checks = []
with httpx.Client(base_url=args.api, timeout=120) as client:

    def call(method, path, data=None, expected=200):
        response = client.request(method, path, json=data)
        assert response.status_code == expected, (path, response.status_code, response.text[:500])
        checks.append({"path": path, "status": response.status_code})
        return response

    assert call("GET", "/health").json()["status"] == "ready"
    info = call("GET", "/model-info").json()
    assert all(v["available"] for v in info["models"].values())
    profiles = call("GET", "/demo-profiles").json()
    sme = {
        "sme_id": "LIVE-VERIFICATION",
        "sector": "Services",
        "annual_revenue": 4500000.0,
        "debt_ratio": 0.42,
        "current_ratio": 1.85,
        "requested_amount": 500000.0,
        "loan_term_months": 36,
        "past_defaults": 0,
    }
    first = call("POST", "/predict/sme", sme).json()
    assert first["prediction"]["model_name"] == "polish_bankruptcy_simplified_1y"
    altered = {
        **sme,
        "annual_revenue": 1.0,
        "requested_amount": 1.0,
        "past_defaults": 8,
        "loan_term_months": 120,
        "sme_id": "OTHER",
        "sector": "Other",
    }
    second = call("POST", "/predict/sme", altered).json()
    assert first["prediction"]["probability"] == second["prediction"]["probability"]
    for profile in profiles:
        full = {"features": profile["features"]}
        prediction = call("POST", "/predict/bankruptcy/full", full).json()
        assert prediction["model_name"] == "polish_bankruptcy_full_1y"
        call("POST", "/explain/bankruptcy/full", full)
    full = {"features": profiles[0]["features"]}
    credit = {
        "GrAppv": 100000.0,
        "SBA_Appv": 75000.0,
        "NoEmp": 10.0,
        "NAICS2": "54",
        "NewExist": "1",
        "State": "CA",
        "UrbanRural": "1",
        "LowDoc": "N",
        "RevLineCr": "N",
    }
    assert call("POST", "/predict/credit", credit).json()["predicted_event"] == "loan_charge_off"
    call("POST", "/explain/sme", sme)
    call("POST", "/explain/credit", credit)
    invalid = {"features": {k: v for k, v in full["features"].items() if k != "Attr64"}}
    call("POST", "/predict/bankruptcy/full", invalid, 422)
    batch = call(
        "POST",
        "/predict/batch",
        {
            "task": "sme",
            "rows": [sme, {"sme_id": "INVALID"}],
            "persist": True,
            "portfolio_name": "Vérification intégration",
        },
    ).json()
    assert batch["valid_rows"] == 1
    call("GET", f"/portfolio/analytics?portfolio_id={batch['portfolio_id']}")
    call("POST", "/assessments", {"input": sme})
    call("GET", "/assessments?sme_id=LIVE-VERIFICATION")
    call(
        "POST", "/financial-analysis", {"total_assets": 100, "total_liabilities": 42, "equity": 58}
    )
    simulation = call(
        "POST",
        "/simulate",
        {
            "principal": 100000,
            "months": 36,
            "annual_rate": 0.07,
            "assumed_annual_credit_pd": 0.05,
            "assumed_lgd": 0.45,
        },
    ).json()
    assert abs(simulation["credit_loss_scenario"]["expected_loss"] - 2250) < 1e-6
    call(
        "POST",
        "/management/rollback",
        {"task": "sme", "reason": "Unauthorized integration check"},
        403,
    )
    out = ROOT / "output/pdf"
    out.mkdir(parents=True, exist_ok=True)
    for route, payload, name in [
        ("/reports/sme.pdf", sme, "assessment-sme.pdf"),
        ("/reports/bankruptcy/full.pdf", full, "assessment-full.pdf"),
        ("/reports/credit.pdf", credit, "assessment-credit.pdf"),
    ]:
        content = call("POST", route, payload).content
        assert content.startswith(b"%PDF")
        (out / name).write_bytes(content)
save_json(
    ROOT / "reports/generated/live_integration.json",
    {
        "executed": True,
        "checks": checks,
        "models": {
            k: {"name": v["model_name"], "version": v["version"]} for k, v in info["models"].items()
        },
        "sme_probability": first["prediction"]["probability"],
    },
)
print(json.dumps({"passed_live_checks": len(checks), "real_models": 3}))
