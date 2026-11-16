"""Strict public contracts for the three distinct prediction tasks."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fintech_risk.features import POLISH_FEATURES

Finite = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class SMEInput(StrictModel):
    sme_id: str = Field(min_length=1, max_length=80)
    sector: str = Field(min_length=1, max_length=100)
    annual_revenue: NonNegative
    debt_ratio: NonNegative = Field(description="Total liabilities / total assets, not debt/equity")
    current_ratio: NonNegative = Field(description="Current assets / short-term liabilities")
    requested_amount: Positive
    loan_term_months: int = Field(gt=0, le=600, strict=True)
    past_defaults: int = Field(ge=0, le=10000, strict=True)


class FullPolishInput(StrictModel):
    features: dict[str, Finite]

    @model_validator(mode="after")
    def complete_features(self):
        missing = sorted(set(POLISH_FEATURES) - self.features.keys())
        extra = sorted(self.features.keys() - set(POLISH_FEATURES))
        if missing or extra:
            raise ValueError(f"Missing features: {missing}; unexpected features: {extra}")
        return self


class CreditInput(StrictModel):
    GrAppv: Positive = Field(description="Approved gross loan amount in historical USD")
    SBA_Appv: Positive = Field(description="Approved SBA guarantee amount, not realized recovery")
    NoEmp: int = Field(ge=0, description="Employee count; fractional values are invalid")
    NAICS2: str = Field(pattern=r"^(UNKNOWN|[1-9][0-9])$")
    NewExist: Literal["1", "2", "UNKNOWN"]
    State: str = Field(pattern=r"^([A-Z]{2}|UNKNOWN)$")
    UrbanRural: Literal["1", "2", "UNKNOWN"]
    LowDoc: Literal["Y", "N", "UNKNOWN"]
    RevLineCr: Literal["Y", "N", "UNKNOWN"]

    @model_validator(mode="after")
    def guarantee(self):
        if self.SBA_Appv > self.GrAppv:
            raise ValueError("SBA approved guarantee cannot exceed gross approved amount")
        return self

    def features(self):
        return {**self.model_dump(), "guarantee_ratio": self.SBA_Appv / self.GrAppv}


class BatchInput(StrictModel):
    task: Literal["sme", "bankruptcy_full", "credit"]
    rows: list[dict] = Field(min_length=1, max_length=1000)
    persist: bool = False
    portfolio_name: str = Field(default="Portefeuille", min_length=1, max_length=100)


class AccountingInput(StrictModel):
    total_assets: NonNegative | None = None
    total_liabilities: NonNegative | None = None
    financial_debt: NonNegative | None = None
    equity: Finite | None = None
    current_assets: NonNegative | None = None
    current_liabilities: NonNegative | None = None
    inventory: NonNegative | None = None
    operating_receivables: NonNegative | None = None
    operating_payables: NonNegative | None = None
    long_term_capital: Finite | None = None
    fixed_assets: NonNegative | None = None


class SimulationInput(StrictModel):
    principal: Positive
    months: int = Field(gt=0, le=600, strict=True)
    annual_rate: Probability = 0.07
    assumed_annual_credit_pd: Probability | None = None
    assumed_lgd: Probability = 0.45
    assumed_ead: NonNegative | None = None
    base_rate: Probability = 0.03
    operating_margin: Probability = 0.02
    baseline_sme: SMEInput | None = None
    scenario_sme: SMEInput | None = None
    baseline_credit: CreditInput | None = None
    scenario_credit: CreditInput | None = None


class ManagementInput(StrictModel):
    task: Literal["sme", "bankruptcy_full", "credit"]
    candidate_path: str | None = None
    reason: str = Field(min_length=5, max_length=500)


class SavedAssessment(StrictModel):
    input: SMEInput
