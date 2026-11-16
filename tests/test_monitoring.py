import pandas as pd

from fintech_risk.config import parameters
from fintech_risk.monitoring import feature_drift


def test_drift_unchanged_and_shifted():
    reference = pd.DataFrame(
        {"Attr2": [0.1, 0.2, 0.3, 0.4] * 100, "Attr4": [1.0, 2.0, 3.0, 4.0] * 100}
    )
    settings = parameters()["drift"]
    assert not any(v["drifted"] for v in feature_drift(reference, reference, settings).values())
    assert all(v["drifted"] for v in feature_drift(reference, reference + 10, settings).values())
