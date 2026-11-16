"""Real Streamlit behavior checks against the running FastAPI service, no HTTP mocks."""

import httpx
from streamlit.testing.v1 import AppTest

from fintech_risk.config import ROOT, save_json

app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=90)
checks = []


def run(label):
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    checks.append(label)


def button(label):
    return next(b for b in app.button if b.label == label)


def navigate(label):
    app.sidebar.radio[0].set_value(label)
    run(label)


run("main_initial")
assert len(app.text_input) == 2 and len(app.number_input) == 6
button("Analyser le risque PME").click()
run("main_real_ml_prediction")
assert any(m.label == "Probabilité estimée" for m in app.metric)
navigate("Analyse financière avancée")
method = next(r for r in app.radio if r.label == "Mode de saisie")
method.set_value("Formulaire complet")
run("full_manual_visible")
assert len(app.number_input) == 64
profile = httpx.get("http://127.0.0.1:8000/demo-profiles").json()[0]["features"]
for widget in app.number_input:
    widget.set_value(float(profile[widget.key.removeprefix("manual")]))
button("Analyser les 64 ratios").click()
run("full_manual_real_prediction")
next(r for r in app.radio if r.label == "Mode de saisie").set_value("Profils de démonstration")
run("full_demo_visible")
button("Exécuter le modèle sur cet exemple").click()
run("full_demo_real_prediction")
navigate("Évaluation crédit avancée")
button("Évaluer le prêt approuvé").click()
run("credit_real_prediction")
navigate("Simulateur financier")
button("Calculer et comparer le risque de faillite").click()
run("accounting_and_sensitivity")
navigate("Analyse de portefeuille")
navigate("Modèles & MLOps")
button("Charger le registre").click()
run("registry_versions")
save_json(
    ROOT / "reports/generated/dashboard_behavior.json",
    {
        "executed": True,
        "checks": checks,
        "main_fields": 8,
        "full_manual_fields": 64,
        "http_mocks": False,
        "csv_note": "File upload is verified separately with the browser integration test.",
    },
)
print(f"Dashboard checks passed: {len(checks)}")
