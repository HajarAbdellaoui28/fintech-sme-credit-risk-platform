# CODEX MASTER PROMPT — FinTech SME Credit Risk Analytics Platform

## 1. Your Role

Act as a Senior Machine Learning Engineer, MLOps Engineer, Data Scientist, and Software Architect.

Design and implement a production-oriented, end-to-end FinTech platform for SME credit risk assessment and corporate bankruptcy risk analysis. This is an academic engineering project, but it must follow professional practices for software engineering, ML evaluation, reproducibility, security, MLOps, and CI/CD.

**START IN PLAN MODE. DO NOT IMPLEMENT ANYTHING UNTIL I APPROVE THE INITIAL PLAN.** Once approved, execute the entire project autonomously in three broad stages, without requesting approval after each stage. Stop only for genuine blockers, required external authorization, or destructive actions.

Write explanations, planning documents, technical reports, and progress summaries for me in **French**. Code, identifiers, commit messages, and technical documentation may be in English.

## 2. Project Context and Objectives

Project name: **FinTech SME Credit Risk Analytics Platform**.

The original academic assignment requests an automated SME credit scoring platform using PySpark MLlib, XGBoost, FastAPI, SHAP, financial risk analysis, grades A–F, simulated risk-adjusted interest rates, Streamlit, ROC-AUC, PR-AUC, cost-sensitive decision thresholds, and Basel-related concepts. It specifies a target inference latency below 100 ms; benchmark this target rather than promising it.

Extend this assignment into an **end-to-end ML and MLOps project**: ingestion, validation, feature engineering, training, evaluation, calibration, experiment tracking, model registry, explainability, API, dashboard, Docker deployment, CI/CD, data drift detection, and controlled retraining.

This is a **decision-support prototype**, not a certified banking decision system. Never claim Basel regulatory compliance without a justified, documented compliance assessment.

## 3. Core Architecture: Two Independent ML Models

### Model 1 — SME Credit Risk Prediction

Dataset: **SBA National (Small Business Administration Loans)**, approximately 899,000 historical loans, subject to verification.

Objective: predict **loan charge-off risk**, not generic corporate bankruptcy. Investigate the target `MIS_Status`, including `CHGOFF` and `PIF`, label completeness, loan maturity, censoring, selection bias from historically approved loans, and the prediction time point.

Potential inputs: `NAICS`, `Term`, `NoEmp`, `NewExist`, geographic and loan-program information, SBA guarantee information, and loan amount where available at the defined prediction time.

**Perform a strict data leakage audit.** Exclude post-outcome variables such as charge-off date, charge-off principal, outcome-related balances, and the target itself. Distinguish `GrAppv` (approved amount) from the originally requested amount; do not silently treat them as equivalent. Document any mismatch between model training inputs and the application's pre-approval use case.

### Model 2 — Corporate Bankruptcy Risk Prediction

Dataset: **Polish Companies Bankruptcy (UCI)**, multiple horizon-specific subsets with approximately 64 financial indicators, subject to inspection.

Objective: predict **corporate bankruptcy risk** using documented financial ratios. Inspect all subsets, labels, feature definitions, time horizons, and potential overlap before selecting a reproducible training strategy. Do not pool cohorts unless methodologically justified. Do not invent meanings for features.

### Fundamental separation

The two models predict **different outcomes** on **different populations and potentially different horizons**. Never join their rows, add or average their predicted probabilities, or call a merged output a calibrated risk probability. The dashboard may display both predictions side by side, with distinct labels, assumptions, explanations, and limitations. If one model lacks required inputs, return a clear unavailable result rather than inventing values.

## 4. Data Engineering

Use **PySpark** for data ingestion, cleaning, validation, transformation, and feature engineering. Implement:

- Dataset inspection, schema and data dictionary documentation.
- Missing values, duplicates, outliers, target balance, and class imbalance analysis.
- Financial feature engineering and categorical encoding where appropriate.
- Data quality checks (Pandera, Great Expectations, or another justified approach).
- Reproducible train/validation/test splits, time-aware when appropriate.
- Prevention of preprocessing leakage and training-serving skew.
- Immutable raw data, lineage, provenance, and licensing documentation.
- **DVC** tracking for datasets, configurations, and pipeline stages, with a suitable remote storage strategy.

Investigate label maturity and censoring in SBA; verify cohort semantics and temporal structure for Polish data. Do not fit transformations on validation/test data. Never commit large raw datasets to Git.

## 5. Machine Learning

For **each** prediction task, compare:

1. Logistic Regression (interpretable baseline)
2. Random Forest
3. XGBoost

LightGBM is optional if justified. Use scikit-learn, XGBoost, Optuna, suitable cross-validation, class imbalance strategies, and probability calibration when needed.

Evaluate ROC-AUC, PR-AUC, precision, recall, F1, confusion matrices, Brier score, calibration curves, and cost-sensitive decision metrics where applicable. Select models using validation data; keep the final test set untouched until final evaluation. Document false-positive/false-negative trade-offs, class prevalence, and the limitations of predicted probabilities.

Use full eligible datasets for final runs when feasible. Small samples are allowed for development smoke tests but must never be represented as final full-data results.

## 6. Financial Risk and Decision Engine

Create a separate, transparent, configurable **decision-support engine** for:

- Grades A–F and documented grade thresholds.
- Configurable credit decision thresholds and manual-review recommendations.
- Risk-adjusted interest-rate **simulations** based on explicit business assumptions.
- Expected loss estimates: `EL = PD × LGD × EAD`.
- Sensitivity analysis, scenario comparisons, portfolio risk segmentation, and a cost matrix.

Distinguish model-estimated PD from assumed or separately estimated LGD and EAD. Never present hypothetical pricing or loss parameters as observed bank policy. Do not automatically make binding lending decisions.

## 7. Complementary Financial Analysis

The original assignment requests `annual_revenue`, `debt_ratio`, `current_ratio`, debt/equity, working-capital coverage, and `past_defaults`. These are not all present in SBA National.

Build a **separate financial-analysis module** that accepts user-entered accounting inputs and computes ratios using documented formulas. Allow explicitly labeled synthetic SME profiles for UI demonstrations and automated tests, but do not train the real SBA model on fabricated financial variables or claim improved empirical predictive power from synthetic values.

For Polish Bankruptcy inference, require the **actual documented features** used by the trained model, via a validated form or structured file import. If inputs are missing, return an explicit validation error or unavailable prediction rather than arbitrary imputations. Keep model-based predictions distinct from rule-based financial simulations.

## 8. Explainable AI

Use **SHAP** for both models:

- Global feature importance and summary plots.
- Local explanations and waterfall plots.
- Model-specific interpretation and financial context.
- Caching or asynchronous execution where appropriate for expensive explanations.

Explain associations and model contributions, not causal effects. Clearly identify which model each explanation belongs to.

## 9. FastAPI Backend

Develop a modular **FastAPI** service with Pydantic schemas, consistent preprocessing, input validation, structured errors, OpenAPI documentation, configuration management, secure environment variables, model version reporting, and privacy-conscious logs.

Suggested routes:

- `GET /health`
- `GET /model-info`
- `POST /predict/credit`
- `POST /predict/bankruptcy`
- `POST /predict/combined` (returns two **separate** predictions)
- `POST /predict/batch`
- `POST /explain/credit`
- `POST /explain/bankruptcy`
- `POST /financial-analysis`
- `POST /simulate`
- `GET /portfolio/analytics`

Load trained models and preprocessing artifacts at startup; do not train during API startup or requests. Benchmark model-only and full API latency separately, including the assignment's <100 ms target where feasible.

## 10. Streamlit Dashboard

Build a polished, consistent, responsive **Streamlit** application with these pages:

### Page 1 — SME Credit Assessment

SME and loan inputs; financial input form; both model predictions when sufficient inputs exist; grades A–F; rule-based recommendations; SHAP explanations; expected loss assumptions; downloadable assessment report.

### Page 2 — Financial Scenario Simulator

Simulate changes in loan amount, duration, revenue, debt, equity, liquidity, and working capital. Distinguish actual model-supported prediction changes from financial rules. Do not imply causal effects.

### Page 3 — Portfolio Risk Analytics

Portfolio composition, score distribution, sector breakdown, expected loss scenarios, risk matrix, decision threshold sensitivity, batch scoring, and downloadable results.

### Page 4 — Model Management

Model metrics, MLflow experiments, registered versions, champion status, drift reports, retraining history, and evaluation artifacts. Protect any management actions requiring authorization.

## 11. MLOps

### MLflow

Track experiments, hyperparameters, metrics, artifacts, model signatures, registered versions, champion aliases, and rollback. Maintain separate registered models for credit and bankruptcy risk.

### DVC

Version data and configurations; create reproducible preprocessing, training, and evaluation stages. Document the DVC remote setup and avoid storing secrets in the repository.

### Evidently: data drift only

Implement reference/current dataset comparisons, drift reports, configurable thresholds, historical reports, and retraining recommendations. Distinguish input drift from performance degradation, which requires later-observed labels. **Do not implement Prometheus, Grafana, or technical infrastructure monitoring.**

### Controlled retraining

Validate new data and label maturity, preprocess, train candidate models, evaluate against the champion, register validated candidates, require appropriate promotion approval or gates, and support rollback. **Never automatically promote a model based solely on detected drift.**

## 12. Docker and Deployment

Use **Docker** and **Docker Compose** for FastAPI, Streamlit, PostgreSQL (where needed), and MLflow. Keep expensive PySpark training separate from routine application startup; use Compose profiles or standalone training commands to fit local resources.

Target environment: Windows, PowerShell, Docker Desktop with WSL2, 8 CPUs, approximately 7.65 GiB RAM allocated to Docker. Avoid unnecessary Kubernetes or microservices. Provide reproducible local startup and an optional cloud deployment strategy without assuming credentials exist.

## 13. CI/CD — GitHub Actions

### Continuous Integration

On pull requests and relevant pushes, run formatting/lint checks (Ruff), unit tests, API integration tests, small-fixture data/schema tests, ML smoke tests, dependency/security checks, and Docker build validation. **Do not run expensive full retraining on every pull request.**

### Continuous Delivery

Build versioned images, run smoke tests, optionally publish to a registry, deploy to staging where configured, verify health, and support controlled production deployment. Never invent cloud credentials; use GitHub Actions secrets. Do not push to a remote or deploy externally without explicit authorization.

### Model delivery

Provide a distinct workflow for candidate training/evaluation, model registration, approval, approved model deployment, and rollback.

## 14. Testing and Quality

Use **Pytest** for unit, data-validation, feature-engineering, prediction, API, integration, financial calculation, explanation, batch-scoring, and Docker smoke tests. Prefer deterministic small fixtures for CI. Verify training/inference preprocessing parity. Never disable failing tests or replace real functionality with mocks merely to report success.

## 15. Reproducibility, Security, and Documentation

Provide pinned/controlled dependencies, documented run commands, random seeds where appropriate, data dictionaries, model cards, dataset provenance/licensing, `.env.example`, `.gitignore`, DVC configuration, experiment and evaluation reports, API docs, architecture diagrams or descriptions, deployment guide, and a complete README.

Never hardcode secrets or expose sensitive financial data in logs. Keep raw datasets and large artifacts outside Git. Document known limitations and the academic/prototype scope.

## 16. Local Development Environment

- Windows and PowerShell; VS Code and Codex.
- Python 3.12.1 (default), Python **3.11.2** installed (preferred for this project).
- Java **17.0.13**.
- Git **2.53.0**.
- Docker **28.0.4**; Docker Compose **v2.34.0**.
- Docker Desktop / WSL2; 8 CPUs, approximately **7.65 GiB RAM**.

Use a project-local `.venv` with Python 3.11 unless compatibility checks justify otherwise. Verify PySpark/Java/Python compatibility and pin suitable versions. Do not modify global Python installations.

## 17. Expected Repository Structure

Propose a modular structure, adjusting if justified:

```text
fintech-sme-credit-risk-platform/
├── data/
│   ├── raw/
│   │   ├── sba/
│   │   └── polish/
│   ├── interim/
│   └── processed/
├── notebooks/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   │   ├── credit/
│   │   └── bankruptcy/
│   ├── explainability/
│   ├── risk/
│   └── monitoring/
├── api/
├── dashboard/
├── tests/
├── configs/
├── reports/
├── docs/
├── scripts/
├── .github/workflows/
├── Dockerfile
├── docker-compose.yml
├── dvc.yaml
├── params.yaml
├── pyproject.toml
└── README.md
```

Avoid unnecessary microservices and overengineering.

## 18. Implementation Strategy — Autonomous End-to-End Development

I want you to implement this entire project **as autonomously as possible**, with minimal manual intervention. Do not divide implementation into many small phases requiring my approval.

**After I approve the initial architecture and feasibility plan, execute the following three broad stages automatically.** Internally use smaller milestones and quality gates as needed, but do not pause for routine approvals.

### Stage 1 — Data Engineering, Machine Learning & MLOps Foundations

Implement:

- Project structure, configuration, environment setup, dependency management, and baseline tests.
- Data ingestion, validation, EDA, cleaning, and feature engineering with PySpark.
- Reproducible preprocessing and splitting for both datasets.
- Independent SBA credit risk and Polish bankruptcy pipelines.
- Logistic Regression, Random Forest, XGBoost, Optuna, evaluation, calibration, and SHAP.
- MLflow tracking, model registry, and champion management.
- DVC dataset/pipeline versioning.
- Financial risk engine and transparent decision rules.

Run appropriate tests, investigate failures, fix issues, and rerun checks before continuing.

### Stage 2 — Backend, Dashboard & Deployment

Implement:

- Complete FastAPI backend and endpoints.
- Validated model loading and inference pipelines.
- Individual and batch scoring.
- Financial analysis and scenario simulation.
- All specified Streamlit pages, SHAP visualizations, and reports.
- PostgreSQL persistence where justified.
- Dockerfiles and Docker Compose.
- Local deployment, integration tests, and end-to-end verification.

Verify the frontend, backend, models, and database work together correctly.

### Stage 3 — CI/CD, Drift Monitoring, Retraining & Final Validation

Implement:

- GitHub Actions CI/CD and security/quality checks.
- Automated unit, integration, API, data, and ML tests.
- Docker image builds and deployment workflows.
- Evidently data drift reports and configurable alerts/recommendations.
- Controlled retraining, candidate evaluation, model promotion gates, and rollback.
- Reproducibility checks and API performance benchmarks.
- Complete README, architecture, model cards, and technical documentation.
- Final end-to-end verification.

**Exclude Prometheus, Grafana, and unnecessary technical infrastructure monitoring.**

### Autonomous Execution Rules

1. **Execute continuously:** After the initial plan is approved, proceed through all three stages without asking for approval after each feature, module, or stage.
2. **Test and repair:** Implement, test, diagnose, fix, and retest each major component. Do not equate code creation with successful validation.
3. **Resolve routine issues:** Handle dependency conflicts, compatibility problems, implementation bugs, and configuration issues independently. Prefer maintainable solutions over shortcuts.
4. **Preserve requirements:** Do not silently omit major features, disable tests, suppress errors, or substitute mocks for production functionality to claim success.
5. **Preserve ML integrity:** Never fabricate data, results, evaluations, or completed tests. Prevent leakage and keep the two models independent.
6. **Be resource-aware:** Avoid concurrent heavy workloads. Use representative samples for smoke tests, full eligible datasets for final evaluation when feasible, and clearly report resource-limited runs.
7. **Minimize interruptions:** Choose sensible defaults and document them. Stop only for missing essential datasets/credentials, truly ambiguous critical requirements, destructive or irreversible actions, external authorization, or unresolved methodological blockers.
8. **Track progress:** Maintain a concise implementation status document with completed work, tests, blockers, and remaining work. Use meaningful local Git commits when appropriate; do not push remotely or deploy to external production without explicit authorization.
9. **Verify completion:** Confirm both ML pipelines execute, models are evaluated and registered, API and dashboard work, Docker Compose starts the application, tests pass, CI/CD is configured, and drift/retraining workflows are demonstrably functional. Distinguish **executed and verified** workflows from **configured but not executed** workflows.
10. **Deliver a French final report:** Architecture, implemented features, model metrics, MLOps/CI/CD, tests and evidence, deployment commands, limitations, and any remaining manual actions.

The goal is a **complete, tested, reproducible, operational end-to-end ML/MLOps project** with minimal user intervention. Do not stop after scaffolding or planning once the initial plan is approved. Continue until completion or a genuine blocker.

## 19. Immediate Task — PLAN MODE ONLY

**Do not implement yet.** Before any code changes:

1. Inspect the repository and available files.
2. Check whether SBA and Polish datasets are present and readable.
3. Inspect the original academic assignment PDF if provided.
4. Audit dataset schemas, labels, feature definitions, horizons, and quality.
5. Identify missing features, leakage, censoring, and selection-bias risks.
6. Assess feasibility of both models and their respective inference contracts.
7. Explain how financial analysis and scenario simulation work without fabricating historical data.
8. Propose the final software architecture and the two independent ML pipelines.
9. Propose the MLOps architecture, DVC storage strategy, Docker layout, and CI/CD approach.
10. Define dashboard pages, API contracts, and test strategy.
11. Present the three-stage implementation roadmap, internal quality gates, and acceptance criteria.
12. Identify unresolved decisions, blockers, and required manual inputs.

If datasets are missing, do not fabricate inspection results: list the exact files needed and label the architecture provisional. If the PDF is missing, identify assumptions and ask for it when necessary. Distinguish verified dataset facts from assumptions.

During Plan Mode, **do not install dependencies, create or modify files, train models, or execute destructive commands**.

### Expected first response (in French)

1. Résumé de compréhension du projet.
2. Audit des datasets et analyse de faisabilité.
3. Architecture End-to-End proposée.
4. Stack technique définitive et justifications.
5. Architecture des deux modèles ML.
6. Architecture MLOps et CI/CD.
7. Fonctionnalités et pages du dashboard.
8. Plan d'implémentation en **trois grandes étapes autonomes**.
9. Risques techniques et méthodologiques.
10. Questions ou décisions réellement bloquantes.

**First present the complete architecture and implementation plan for my approval. Once approved, execute all three implementation stages autonomously, without requiring additional approval between stages.**
