import pytest

from fintech_risk.finance import accounting, expected_loss, grade, pricing, repayment


def test_amortization_and_zero_rate():
    assert repayment(1200, 12, 0)["monthly_payment"] == 100
    assert repayment(100000, 36, 0.07)["monthly_payment"] == pytest.approx(3087.709686, rel=1e-6)


def test_expected_loss_requires_credit_probability():
    assert expected_loss(0.1, 0.45, 100000)["expected_loss"] == pytest.approx(4500)
    with pytest.raises(ValueError):
        expected_loss(0.1, 0.45, 100000, "corporate_bankruptcy")


def test_accounting_undefined_and_negative_equity():
    result = accounting(
        {
            "financial_debt": 100,
            "equity": -50,
            "current_assets": 100,
            "current_liabilities": 0,
            "inventory": 20,
            "operating_receivables": 30,
            "operating_payables": 10,
            "long_term_capital": 80,
            "fixed_assets": 60,
        }
    )
    assert result["debt_to_equity"]["value"] == -2
    assert result["current_ratio"]["value"] is None
    assert result["bfr_coverage"]["value"] == 0.5


def test_grades_and_pricing():
    assert [grade(p) for p in [0, 0.02, 0.05, 0.1, 0.2, 0.35]] == list("ABCDEF")
    assert pricing(0.03, 0.02, 0.1, 0.45)["annual_rate_simulated"] == pytest.approx(0.095)
    with pytest.raises(ValueError):
        grade(float("nan"))
