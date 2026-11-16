import pytest


def test_eight_field_form_real_prediction_and_six_fields_do_not_affect_ml(client, sme):
    first = client.post("/predict/sme", json=sme)
    assert first.status_code == 200, first.text
    altered = {
        **sme,
        "sme_id": "OTHER",
        "sector": "Manufacturing",
        "annual_revenue": 1.0,
        "requested_amount": 1.0,
        "loan_term_months": 120,
        "past_defaults": 7,
    }
    second = client.post("/predict/sme", json=altered).json()
    assert first.json()["prediction"]["probability"] == second["prediction"]["probability"]
    assert first.json()["explanation"]["values"] == second["explanation"]["values"]
    assert second["financial_analysis"]["alerts"]
    assert second["prediction"]["predicted_event"] == "corporate_bankruptcy"
    assert "SYNTHETIC TEST FIXTURE" in second["prediction"]["warnings"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("debt_ratio", -1),
        ("current_ratio", None),
        ("loan_term_months", 0),
        ("past_defaults", -1),
        ("annual_revenue", -1),
        ("sme_id", ""),
    ],
)
def test_sme_validation(client, sme, field, value):
    assert client.post("/predict/sme", json={**sme, field: value}).status_code == 422


def test_full_polish_requires_all_features(client, fixture_data):
    frame, _ = fixture_data
    row = frame.iloc[0].to_dict()
    assert client.post("/predict/bankruptcy/full", json={"features": row}).status_code == 200
    row.pop("Attr64")
    assert client.post("/predict/bankruptcy/full", json={"features": row}).status_code == 422


def test_sba_contract_and_independent_event(client, credit):
    response = client.post("/predict/credit", json=credit)
    assert response.status_code == 200, response.text
    assert response.json()["predicted_event"] == "loan_charge_off"
    assert response.json()["horizon"] != "1_year"
    assert client.post("/predict/credit", json={**credit, "SBA_Appv": 200000}).status_code == 422
    assert client.post("/predict/credit", json={**credit, "requested_amount": 1}).status_code == 422


def test_batch_row_errors_persistence_and_analytics(client, sme):
    response = client.post(
        "/predict/batch", json={"task": "sme", "rows": [sme, {"sme_id": "bad"}], "persist": True}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid_rows"] == 1
    assert body["rows"][1]["status"] == "invalid"
    analytics = client.get(f"/portfolio/analytics?portfolio_id={body['portfolio_id']}")
    assert analytics.status_code == 200
    assert analytics.json()["grade_distribution"]
    assert analytics.json()["invalid_rows"] == 1


def test_simulation_never_uses_bankruptcy_as_credit_pd(client, sme):
    response = client.post(
        "/simulate",
        json={
            "principal": 1000,
            "months": 12,
            "annual_rate": 0,
            "baseline_sme": sme,
            "scenario_sme": {**sme, "annual_revenue": 1.0, "requested_amount": 1.0},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert not data["credit_loss_scenario"]["available"]
    assert (
        data["baseline_sme"]["prediction"]["probability"]
        == data["scenario_sme"]["prediction"]["probability"]
    )


def test_management_requires_authentication(client):
    payload = {"task": "sme", "reason": "Test unauthorized action"}
    assert client.post("/management/rollback", json=payload).status_code == 403


def test_saved_assessment_requires_explicit_action(client, sme):
    assert client.get("/assessments", params={"sme_id": sme["sme_id"]}).json() == []
    client.post("/predict/sme", json=sme)
    assert client.get("/assessments", params={"sme_id": sme["sme_id"]}).json() == []
    assert client.post("/assessments", json={"input": sme}).status_code == 200
    assert len(client.get("/assessments", params={"sme_id": sme["sme_id"]}).json()) == 1


def test_model_info_and_health(client):
    assert client.get("/health").json()["status"] == "ready"
    assert len(client.get("/model-info").json()["models"]) == 3
