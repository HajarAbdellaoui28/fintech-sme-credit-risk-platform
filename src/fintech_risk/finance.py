"""Transparent accounting calculations and hypothetical financing, never invented ML."""

import math

from fintech_risk.config import parameters


def grade(probability, boundaries=None):
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Probability must be finite and between 0 and 1")
    boundaries = boundaries or parameters()["decision"]["grade_boundaries"]
    return "ABCDEF"[sum(probability >= v for v in boundaries)]


def ratio(numerator, denominator):
    if numerator is None or denominator is None:
        return {"value": None, "reason": "Données comptables manquantes"}
    if denominator == 0:
        return {"value": None, "reason": "Dénominateur nul"}
    return {"value": numerator / denominator, "reason": None}


def analyse_sme(inputs):
    data = inputs.model_dump() if hasattr(inputs, "model_dump") else inputs
    alerts = []
    if data["past_defaults"]:
        alerts.append(
            "Incidents passés déclarés : revue manuelle recommandée, sans effet sur la probabilité ML."
        )
    if data["current_ratio"] < 1:
        alerts.append("Actif courant inférieur aux dettes à court terme.")
    if data["debt_ratio"] > 1:
        alerts.append("Passif total supérieur à l'actif total déclaré.")
    financing = ratio(data["requested_amount"], data["annual_revenue"])
    return {
        "type": "rule_based_financial_analysis",
        "sme_id": data["sme_id"],
        "sector": data["sector"],
        "financing_to_revenue": financing,
        "liabilities_to_assets": data["debt_ratio"],
        "current_ratio": data["current_ratio"],
        "alerts": alerts,
        "recommendation": "Revue humaine ; aucune décision de prêt automatique.",
        "ml_inputs_only": ["debt_ratio", "current_ratio"],
        "expected_credit_loss": {
            "available": False,
            "reason": "Une probabilité de faillite ne constitue pas une PD de crédit validée.",
        },
        "loan_repayment_simulation": repayment(
            data["requested_amount"], data["loan_term_months"], 0.07
        ),
    }


def accounting(data):
    result = {
        "liabilities_to_assets": ratio(data.get("total_liabilities"), data.get("total_assets")),
        "debt_to_equity": ratio(data.get("financial_debt"), data.get("equity")),
        "current_ratio": ratio(data.get("current_assets"), data.get("current_liabilities")),
    }
    working = (
        data["current_assets"] - data["current_liabilities"]
        if data.get("current_assets") is not None and data.get("current_liabilities") is not None
        else None
    )
    bfr_keys = ["inventory", "operating_receivables", "operating_payables"]
    bfr = (
        data["inventory"] + data["operating_receivables"] - data["operating_payables"]
        if all(data.get(k) is not None for k in bfr_keys)
        else None
    )
    frng = (
        data["long_term_capital"] - data["fixed_assets"]
        if data.get("long_term_capital") is not None and data.get("fixed_assets") is not None
        else None
    )
    result.update(
        {
            "working_capital": working,
            "operating_working_capital_requirement": bfr,
            "frng": frng,
            "bfr_coverage": ratio(frng, bfr),
            "formulas": {
                "working_capital": "current_assets - current_liabilities",
                "bfr": "inventory + operating_receivables - operating_payables",
                "frng": "long_term_capital - fixed_assets",
                "bfr_coverage": "frng / bfr",
            },
            "warnings": ["Ratios négatifs conservés ; interpréter les capitaux propres négatifs."],
        }
    )
    return result


def repayment(principal, months, annual_rate):
    if not math.isfinite(principal) or principal < 0 or months <= 0 or not 0 <= annual_rate <= 1:
        raise ValueError("Invalid financing assumptions")
    monthly_rate = annual_rate / 12
    payment = (
        principal / months
        if monthly_rate == 0
        else principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)
    )
    return {
        "monthly_payment": payment,
        "total_payments": payment * months,
        "financing_cost": payment * months - principal,
        "assumptions": {
            "annual_nominal_rate": annual_rate,
            "months": months,
            "principal": principal,
            "fees": 0,
            "type": "hypothetical_fixed_rate_amortization",
        },
    }


def expected_loss(
    pd_credit, lgd, ead, probability_source="user_assumed_credit_pd", horizon="user_defined"
):
    if probability_source not in {"user_assumed_credit_pd", "sba_historical_chargeoff_scenario"}:
        raise ValueError("Bankruptcy probability cannot be used as credit PD")
    if not all(math.isfinite(v) for v in [pd_credit, lgd, ead]) or not (
        0 <= pd_credit <= 1 and 0 <= lgd <= 1 and ead >= 0
    ):
        raise ValueError("Invalid PD/LGD/EAD")
    return {
        "expected_loss": pd_credit * lgd * ead,
        "formula": "PD * LGD * EAD",
        "pd": pd_credit,
        "lgd_assumed": lgd,
        "ead_assumed": ead,
        "probability_source": probability_source,
        "horizon": horizon,
        "warning": "Simulation, sans estimation empirique de LGD ni conformité réglementaire.",
    }


def pricing(base_rate, operating_margin, annual_credit_pd, lgd):
    if not 0 <= annual_credit_pd <= 1 or not 0 <= lgd <= 1:
        raise ValueError("Invalid annual credit assumptions")
    return {
        "annual_rate_simulated": base_rate + operating_margin + annual_credit_pd * lgd,
        "formula": "base_rate + operating_margin + assumed_annual_credit_pd * assumed_lgd",
        "warning": "Hypothèses annuelles déclarées ; aucune probabilité de faillite utilisée.",
    }
