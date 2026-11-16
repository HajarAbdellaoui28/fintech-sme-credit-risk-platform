import numpy as np
import pytest
from scipy.special import logit

from fintech_risk.features import CREDIT_FEATURES, FORBIDDEN_CREDIT
from fintech_risk.models import RiskModel, build_pipeline, explain


@pytest.mark.parametrize("family", ["logistic", "forest", "xgboost"])
def test_real_estimators_and_preprocessing_parity(fixture_data, family):
    frame, y = fixture_data
    pipe = build_pipeline("sme", family, {"n_estimators": 20}).fit(frame, y)
    model = RiskModel(pipe, ["Attr2", "Attr4"], "sme")
    a = model.predict_proba(frame.head(1))[0, 1]
    b = model.predict_proba(frame.head(8))[0, 1]
    assert a == pytest.approx(b, abs=1e-7)
    assert np.isfinite(a) and 0 <= a <= 1
    np.testing.assert_allclose(
        pipe.named_steps["preprocess"].transform(frame.head(1)),
        pipe.named_steps["preprocess"].transform(frame.head(8))[:1],
    )


def test_shap_additivity(fixture_data):
    frame, y = fixture_data
    model = RiskModel(build_pipeline("sme", "logistic").fit(frame, y), ["Attr2", "Attr4"], "sme")
    result = explain(model, frame.head(2), frame.head(20))
    np.testing.assert_allclose(
        np.array(result["values"]).sum(axis=1) + result["base_value"],
        logit(model.predict_proba(frame.head(2))[:, 1]),
        atol=1e-6,
    )


def test_credit_allowlist_has_no_outcome_features():
    assert not (set(CREDIT_FEATURES) & FORBIDDEN_CREDIT)
