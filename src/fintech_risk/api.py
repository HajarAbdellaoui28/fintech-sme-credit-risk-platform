"""FastAPI application. Start with uvicorn fintech_risk.api:app."""

import json
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from fintech_risk.config import ROOT, read_json
from fintech_risk.database import Assessment, ManagementEvent, Portfolio, engine, session
from fintech_risk.features import polish_dictionary
from fintech_risk.finance import accounting, expected_loss, pricing, repayment
from fintech_risk.schemas import (
    AccountingInput,
    BatchInput,
    CreditInput,
    FullPolishInput,
    ManagementInput,
    SavedAssessment,
    SimulationInput,
    SMEInput,
)
from fintech_risk.service import CONTRACTS, ModelService, ModelUnavailable

logger = logging.getLogger("fintech.api")


@asynccontextmanager
async def lifespan(app):
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    app.state.models = ModelService()
    yield


app = FastAPI(
    title="FinTech SME Risk Analytics",
    version="0.1.0",
    lifespan=lifespan,
    description="Three independent historical risk models. Academic decision support only.",
)


@app.middleware("http")
async def private_request_log(request: Request, call_next):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(Exception)
async def internal_error(request, exc):
    logger.error("Internal operation failed: %s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Operation failed; contact the local operator.",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never echo submitted financial values in validation errors or logs.
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_input",
                "details": [
                    {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(ModelUnavailable)
async def unavailable(request, exc):
    return JSONResponse(
        status_code=503, content={"error": {"code": "model_unavailable", "message": str(exc)}}
    )


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, exc):
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"error": {"code": "persistence_unavailable"}})


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "request_rejected", "message": exc.detail}},
    )


def models(request: Request):
    return request.app.state.models


def admin(x_admin_token: str = Header(default="")):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(403, "Administrator authorization required")
    return x_admin_token


ServiceDependency = Annotated[ModelService, Depends(models)]
AdminDependency = Annotated[str, Depends(admin)]


@app.get("/health")
def health(service: ServiceDependency):
    info = service.info()
    database = "unconfigured"
    if os.environ.get("DATABASE_URL"):
        try:
            with engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            database = "available"
        except SQLAlchemyError:
            database = "unavailable"
    ready = all(v["available"] for v in info.values()) and database == "available"
    return {
        "status": "ready" if ready else "degraded",
        "models": {k: v["available"] for k, v in info.items()},
        "database": database,
    }


@app.get("/model-info")
def model_info(service: ServiceDependency):
    return {
        "models": service.info(),
        "accounting_convention": {
            "debt_ratio": "Total liabilities / total assets",
            "current_ratio": "Current assets / short-term liabilities",
        },
        "polish_dictionary": polish_dictionary(),
    }


@app.post("/predict/sme")
def predict_sme(payload: SMEInput, service: ServiceDependency):
    return service.predict("sme", payload, include_explanation=True)


@app.post("/predict/bankruptcy/full")
def predict_full(payload: FullPolishInput, service: ServiceDependency):
    return service.predict("bankruptcy_full", payload)


@app.post("/predict/credit")
def predict_credit(payload: CreditInput, service: ServiceDependency):
    return service.predict("credit", payload)


@app.post("/explain/sme")
def explain_sme(payload: SMEInput, service: ServiceDependency):
    return service.explanation("sme", payload)


@app.post("/explain/bankruptcy/full")
def explain_full(payload: FullPolishInput, service: ServiceDependency):
    return service.explanation("bankruptcy_full", payload)


@app.post("/explain/credit")
def explain_credit(payload: CreditInput, service: ServiceDependency):
    return service.explanation("credit", payload)


@app.post("/predict/batch")
def predict_batch(payload: BatchInput, service: ServiceDependency):
    service.get(payload.task)
    rows = []
    for index, data in enumerate(payload.rows):
        try:
            validated = CONTRACTS[payload.task].model_validate(data)
            result = service.predict(payload.task, validated)
            rows.append(
                {
                    "index": index,
                    "status": "ok",
                    "sector": data.get("sector", data.get("NAICS2", "Unknown")),
                    "result": result,
                }
            )
        except ValidationError as exc:
            rows.append(
                {
                    "index": index,
                    "status": "invalid",
                    "errors": [
                        {"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()
                    ],
                }
            )
    response = {
        "task": payload.task,
        "rows": rows,
        "valid_rows": sum(r["status"] == "ok" for r in rows),
    }
    if payload.persist:
        with session() as db:
            portfolio = Portfolio(name=payload.portfolio_name, task=payload.task, rows=rows)
            db.add(portfolio)
            db.commit()
            response["portfolio_id"] = portfolio.id
    return response


@app.post("/financial-analysis")
def financial_analysis(payload: AccountingInput):
    return accounting(payload.model_dump())


@app.post("/simulate")
def simulate(payload: SimulationInput, service: ServiceDependency):
    result = {
        "repayment": repayment(payload.principal, payload.months, payload.annual_rate),
        "interpretation": "Simulation financière hypothétique ; les variations ne sont pas causales.",
    }
    if payload.assumed_annual_credit_pd is not None:
        result["credit_loss_scenario"] = expected_loss(
            payload.assumed_annual_credit_pd,
            payload.assumed_lgd,
            payload.assumed_ead if payload.assumed_ead is not None else payload.principal,
            horizon="assumed_1_year",
        )
        result["pricing_scenario"] = pricing(
            payload.base_rate,
            payload.operating_margin,
            payload.assumed_annual_credit_pd,
            payload.assumed_lgd,
        )
    else:
        result["credit_loss_scenario"] = {
            "available": False,
            "reason": "Explicit assumed credit PD required; bankruptcy probabilities are not used.",
        }
    for task in ["sme", "credit"]:
        for side in ["baseline", "scenario"]:
            inputs = getattr(payload, f"{side}_{task}")
            if inputs:
                result[f"{side}_{task}"] = service.predict(task, inputs)
    return result


@app.post("/assessments")
def save_assessment(payload: SavedAssessment, service: ServiceDependency):
    result = service.predict("sme", payload.input)
    with session() as db:
        item = Assessment(
            sme_id=payload.input.sme_id,
            payload={"input": payload.input.model_dump(), "result": result},
        )
        db.add(item)
        db.commit()
        return {"assessment_id": item.id, "sme_id": item.sme_id}


@app.get("/assessments")
def assessment_history(sme_id: str):
    with session() as db:
        records = db.scalars(
            select(Assessment)
            .where(Assessment.sme_id == sme_id)
            .order_by(Assessment.id.desc())
            .limit(100)
        )
        return [{"id": r.id, "at": r.created_at.isoformat(), **r.payload} for r in records]


@app.get("/portfolios")
def portfolios():
    with session() as db:
        return [
            {"id": p.id, "name": p.name, "task": p.task}
            for p in db.scalars(select(Portfolio).order_by(Portfolio.id.desc()).limit(100))
        ]


@app.get("/portfolio/analytics")
def portfolio_analytics(
    portfolio_id: int,
    assumed_credit_pd: float | None = None,
    assumed_lgd: float = 0.45,
    assumed_ead_per_row: float = 100000.0,
):
    with session() as db:
        p = db.get(Portfolio, portfolio_id)
        if not p:
            raise HTTPException(404, "Portfolio not found")
        records = [r for r in p.rows if r["status"] == "ok"]
        values = [r["result"].get("prediction", r["result"]) for r in records]
        probs = np.array([v["probability"] for v in values])
        output = {
            "id": p.id,
            "name": p.name,
            "task": p.task,
            "rows": p.rows,
            "valid_rows": len(records),
            "invalid_rows": len(p.rows) - len(records),
            "mean_probability": float(probs.mean()) if len(probs) else None,
            "grade_distribution": {
                g: sum(v["indicative_grade"] == g for v in values) for g in "ABCDEF"
            },
            "sector_distribution": {
                s: sum(r["sector"] == s for r in records)
                for s in sorted({r["sector"] for r in records})
            },
            "threshold_sensitivity": [
                {"threshold": t, "flagged": int((probs >= t).sum())}
                for t in [0.02, 0.05, 0.1, 0.2, 0.35, 0.5]
            ],
        }
        if assumed_credit_pd is not None:
            try:
                output["credit_loss_scenario"] = expected_loss(
                    assumed_credit_pd,
                    assumed_lgd,
                    assumed_ead_per_row * len(records),
                    horizon="user_assumed_common_horizon",
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return output


@app.get("/demo-profiles")
def demo_profiles():
    path = ROOT / "artifacts/demo_profiles.json"
    return read_json(path) if path.exists() else []


@app.get("/management/reports")
def reports():
    files = sorted(
        p
        for p in (ROOT / "reports/generated/drift").glob("*.json")
        if not p.name.endswith(".evidently.json")
    )
    events = ROOT / "artifacts/management_events.json"
    return {
        "drift": [read_json(p) for p in files[-20:]],
        "events": read_json(events) if events.exists() else [],
    }


@app.get("/management/registry")
def registry_versions():
    import mlflow

    from fintech_risk.config import MODEL_NAMES

    client = mlflow.MlflowClient(
        tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
    )
    rows = []
    for task, name in MODEL_NAMES.items():
        for model in client.search_model_versions(f"name='{name}'"):
            rows.append(
                {
                    "task": task,
                    "name": name,
                    "version": model.version,
                    "status": model.status,
                    "aliases": list(model.aliases or []),
                    "run_id": model.run_id,
                }
            )
    return rows


def audit_management(action, result):
    with session() as db:
        db.add(ManagementEvent(action=action, details=result))
        db.commit()


@app.post("/management/promote", dependencies=[Depends(admin)])
async def promote_model(payload: ManagementInput, request: Request, token: AdminDependency):
    from fintech_risk.registry import promote

    if not payload.candidate_path:
        raise HTTPException(422, "Candidate path required")
    try:
        result = await run_in_threadpool(
            promote, payload.task, ROOT / payload.candidate_path, token, payload.reason
        )
        request.app.state.models = ModelService()
        audit_management(
            "promotion",
            {"task": payload.task, "version": result["version"], "reason": payload.reason},
        )
        return result
    except (ValueError, PermissionError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/management/rollback", dependencies=[Depends(admin)])
async def rollback_model(payload: ManagementInput, request: Request, token: AdminDependency):
    from fintech_risk.registry import rollback

    try:
        result = await run_in_threadpool(rollback, payload.task, token, payload.reason)
        request.app.state.models = ModelService()
        audit_management(
            "rollback",
            {"task": payload.task, "version": result["version"], "reason": payload.reason},
        )
        return result
    except (ValueError, PermissionError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/reports/sme.pdf")
def sme_report(
    payload: SMEInput,
    service: ServiceDependency,
    annual_rate: Annotated[float, Query(ge=0, le=1, allow_inf_nan=False)] = 0.07,
):
    from fintech_risk.reporting import assessment_pdf

    result = service.predict("sme", payload, include_explanation=True)
    result["financial_analysis"]["loan_repayment_simulation"] = repayment(
        payload.requested_amount, payload.loan_term_months, annual_rate
    )
    return Response(
        assessment_pdf("Évaluation PME", result),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="assessment.pdf"'},
    )


@app.post("/reports/bankruptcy/full.pdf")
def full_report(payload: FullPolishInput, service: ServiceDependency):
    from fintech_risk.reporting import assessment_pdf

    return Response(
        assessment_pdf(
            "Analyse financière avancée", service.predict("bankruptcy_full", payload, True)
        ),
        media_type="application/pdf",
    )


@app.post("/reports/credit.pdf")
def credit_report(payload: CreditInput, service: ServiceDependency):
    from fintech_risk.reporting import assessment_pdf

    return Response(
        assessment_pdf("Analyse crédit SBA", service.predict("credit", payload, True)),
        media_type="application/pdf",
    )


@app.get("/models/{task}/global-importance")
def global_importance(task: str, service: ServiceDependency):
    bundle = service.get(task)
    return read_json(bundle["directory"] / "global_shap.json")["mean_absolute_shap"]
