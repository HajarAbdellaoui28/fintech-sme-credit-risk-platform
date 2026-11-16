from fintech_risk.registry import check_promotion


def metadata(ap=0.4, brier=0.05, cost=0.2, development=False):
    return {
        "development_sample": development,
        "features": ["Attr2", "Attr4"],
        "horizon": "1_year",
        "validation": {"pr_auc_average_precision": ap, "brier": brier, "simulated_cost": cost},
    }


def test_promotion_gate_rejects_regression_and_smoke_models():
    assert check_promotion(metadata(), metadata())[0]
    assert not check_promotion(metadata(ap=0.1), metadata())[0]
    assert not check_promotion(metadata(brier=0.2), metadata())[0]
    assert not check_promotion(metadata(development=True), metadata())[0]
