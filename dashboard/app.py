"""French Streamlit client; all scoring and persistence goes through FastAPI."""

import io
import os

import httpx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="FinSight | Risque PME", page_icon="◈", layout="wide")
API = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")
st.markdown(
    """<style>
.stApp {background:#f5f7fb} .block-container {padding-top:4rem;max-width:1400px}
[data-testid="stSidebar"] {background:#101f36} [data-testid="stSidebar"] * {color:#e5edf7}
h1,h2,h3 {color:#142740} [data-testid="stMetric"] {background:white;border:1px solid #e0e6ef;
border-radius:12px;padding:16px} div.stButton>button[kind="primary"]{background:#137c78;border:0}
</style>""",
    unsafe_allow_html=True,
)


def request(method, path, payload=None, token=None, binary=False):
    try:
        response = httpx.request(
            method,
            API + path,
            json=payload,
            timeout=120,
            headers={"X-Admin-Token": token} if token else {},
        )
        if response.is_error:
            st.error(f"La requête a échoué ({response.status_code}).")
            try:
                st.json(response.json())
            except ValueError:
                st.caption("Service momentanément indisponible.")
            return None
        return response.content if binary else response.json()
    except httpx.HTTPError:
        st.error("Connexion à l'API impossible. Vérifiez le démarrage des services.")
        return None


def title(name, subtitle):
    st.caption("FINSIGHT / ANALYTIQUE FINANCIÈRE")
    st.title(name)
    st.write(subtitle)
    st.caption(
        "Prototype académique d'aide à l'analyse. Aucune décision bancaire automatique ni conformité Bâle certifiée."
    )


def display_shap(explanation):
    if not explanation:
        return
    names, values = explanation["feature_names"], explanation["values"][0]
    pairs = sorted(zip(names, values, strict=True), key=lambda p: abs(p[1]), reverse=True)[:12]
    fig = go.Figure(
        go.Waterfall(
            orientation="h",
            y=["Base"] + [p[0] for p in pairs],
            x=[explanation["base_value"]] + [p[1] for p in pairs],
            measure=["absolute"] + ["relative"] * len(pairs),
        )
    )
    fig.update_layout(
        height=350,
        title="Contributions locales SHAP",
        xaxis_title=explanation["scale"],
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        explanation["calibration_note"]
        + " Les contributions décrivent des associations, sans causalité."
    )


def display_prediction(result):
    prediction = result.get("prediction", result)
    cols = st.columns(4)
    cols[0].metric("Probabilité estimée", f"{prediction['probability']:.1%}")
    cols[1].metric("Classe indicative", prediction["indicative_grade"])
    cols[2].metric(
        "Horizon", "1 an" if prediction["horizon"] == "1_year" else "Historique variable"
    )
    cols[3].metric("Version du modèle", prediction["model_version"])
    event = (
        "Faillite de l'entreprise"
        if prediction["predicted_event"] == "corporate_bankruptcy"
        else "Charge-off du prêt"
    )
    st.info(f"Événement prédit : {event}. Classification indicative, non réglementaire.")
    for warning in prediction["warnings"]:
        st.caption(warning)
    if "explanation" in result:
        display_shap(result["explanation"])


def sme_form():
    with st.form("sme-eight-fields"):
        st.subheader("Votre entreprise et votre financement")
        st.caption(
            "Exemple académique prérempli : remplacez ces valeurs pour analyser un dossier réel."
        )
        a, b = st.columns(2)
        sme_id = a.text_input("Identifiant PME", "PME-8842")
        sector = b.text_input("Secteur", "Services")
        annual_revenue = a.number_input(
            "Chiffre d'affaires annuel", min_value=0.0, value=4500000.0, step=10000.0
        )
        debt_ratio = b.number_input(
            "Passif total / actif total",
            min_value=0.0,
            value=0.42,
            step=0.01,
            help="Convention obligatoire : passif total / actif total (Attr2 UCI). Ce ratio n'est pas dette / fonds propres.",
        )
        current_ratio = a.number_input(
            "Actif courant / dettes à court terme",
            min_value=0.0,
            value=1.85,
            step=0.05,
            help="Liquidité générale selon Attr4 UCI. Les ratios ne sont pas exprimés en pourcentage.",
        )
        requested_amount = b.number_input(
            "Montant demandé", min_value=1.0, value=500000.0, step=1000.0
        )
        loan_term_months = a.number_input(
            "Durée du financement (mois)", min_value=1, max_value=600, value=36
        )
        past_defaults = b.number_input(
            "Incidents de paiement passés", min_value=0, max_value=10000, value=0
        )
        submitted = st.form_submit_button("Analyser le risque PME", type="primary")
    return submitted, dict(
        sme_id=sme_id,
        sector=sector,
        annual_revenue=annual_revenue,
        debt_ratio=debt_ratio,
        current_ratio=current_ratio,
        requested_amount=requested_amount,
        loan_term_months=loan_term_months,
        past_defaults=past_defaults,
    )


def report_download(route, payload, key):
    if st.button("Préparer le rapport PDF", key=key):
        pdf = request("POST", route, payload, binary=True)
        if pdf:
            st.download_button(
                "Télécharger le rapport", pdf, f"{key}.pdf", "application/pdf", key=key + "dl"
            )


def credit_form(key="credit"):
    with st.form(key):
        st.caption(
            "Conditions approuvées de démonstration préremplies ; saisissez les conditions réelles du prêt à analyser."
        )
        a, b = st.columns(2)
        amount = a.number_input(
            "Montant approuvé (USD)", min_value=200.0, value=100000.0, key=key + "amt"
        )
        guarantee = b.number_input(
            "Garantie SBA approuvée (USD)", min_value=100.0, value=75000.0, key=key + "gua"
        )
        employees = a.number_input("Nombre d'employés", min_value=0, value=10, key=key + "emp")
        sector = b.text_input("Code NAICS à deux chiffres", "54", key=key + "sector")
        new = a.selectbox(
            "Entreprise",
            ["1", "2", "UNKNOWN"],
            format_func=lambda x: {"1": "Existante", "2": "Nouvelle", "UNKNOWN": "Inconnu"}[x],
            key=key + "new",
        )
        state = b.text_input("État américain (code)", "CA", key=key + "state")
        urban = a.selectbox(
            "Zone",
            ["1", "2", "UNKNOWN"],
            format_func=lambda x: {"1": "Urbaine", "2": "Rurale", "UNKNOWN": "Inconnue"}[x],
            key=key + "urban",
        )
        low = b.selectbox("Programme LowDoc", ["N", "Y", "UNKNOWN"], key=key + "low")
        rev = a.selectbox("Crédit renouvelable", ["N", "Y", "UNKNOWN"], key=key + "rev")
        submitted = st.form_submit_button("Évaluer le prêt approuvé", type="primary")
    return submitted, {
        "GrAppv": amount,
        "SBA_Appv": guarantee,
        "NoEmp": employees,
        "NAICS2": sector,
        "NewExist": new,
        "State": state,
        "UrbanRural": urban,
        "LowDoc": low,
        "RevLineCr": rev,
    }


with st.sidebar:
    st.markdown("## ◈ FinSight")
    st.caption("SME RISK ANALYTICS")
    page = st.radio(
        "Navigation",
        [
            "Évaluation du risque PME",
            "Analyse financière avancée",
            "Évaluation crédit avancée",
            "Simulateur financier",
            "Analyse de portefeuille",
            "Modèles & MLOps",
        ],
    )
    st.divider()
    st.caption("Trois modèles indépendants\nFaillite ≠ charge-off")

if page == "Évaluation du risque PME":
    title(
        "Évaluation du risque PME",
        "Une estimation réelle de faillite à un an, à partir de deux ratios comptables.",
    )
    st.warning(
        "Seuls le passif / actif et la liquidité entrent dans la prédiction ML. Les six autres champs servent à l'analyse financière."
    )
    submitted, payload = sme_form()
    if submitted:
        result = request("POST", "/predict/sme", payload)
        if result:
            st.session_state["sme_assessment"] = (payload, result)
    if "sme_assessment" in st.session_state:
        saved_payload, result = st.session_state["sme_assessment"]
        display_prediction(result)
        analysis = result["financial_analysis"]
        ratio = analysis["financing_to_revenue"]
        st.metric(
            "Financement demandé / chiffre d'affaires",
            f"{ratio['value']:.1%}" if ratio["value"] is not None else "Indisponible",
        )
        for alert in analysis["alerts"]:
            st.warning(alert)
        st.write(analysis["recommendation"])
        st.caption(analysis["expected_credit_loss"]["reason"])
        annual_rate = (
            st.slider("Taux annuel hypothétique pour l'échéancier (%)", 0.0, 30.0, 7.0, 0.25) / 100
        )
        simulation = request(
            "POST",
            "/simulate",
            {
                "principal": saved_payload["requested_amount"],
                "months": saved_payload["loan_term_months"],
                "annual_rate": annual_rate,
            },
        )
        if simulation:
            st.metric("Mensualité simulée", f"{simulation['repayment']['monthly_payment']:,.2f}")
            st.caption(
                "Taux nominal fixe, zéro frais, même unité monétaire pour les montants déclarés."
            )
        a, b = st.columns(2)
        with a:
            report_download(
                f"/reports/sme.pdf?annual_rate={annual_rate}", saved_payload, "evaluation-pme"
            )
        with b:
            if st.button("Enregistrer volontairement ce dossier"):
                record = request("POST", "/assessments", {"input": saved_payload})
                if record:
                    st.success(f"Dossier enregistré : {record['assessment_id']}")
        if st.button("Consulter l'historique de cette PME"):
            import urllib.parse

            st.json(
                request("GET", "/assessments?sme_id=" + urllib.parse.quote(saved_payload["sme_id"]))
            )

elif page == "Analyse financière avancée":
    title(
        "Analyse financière avancée",
        "Le modèle complet utilise 64 variables documentées de la cohorte Polish à un an.",
    )
    info = request("GET", "/model-info")
    dictionary = info["polish_dictionary"] if info else {}
    method = st.radio(
        "Mode de saisie",
        ["Import CSV", "Formulaire complet", "Profils de démonstration"],
        horizontal=True,
    )
    payload = None
    if method == "Import CSV":
        st.download_button(
            "Télécharger le modèle CSV",
            ",".join(f"Attr{i}" for i in range(1, 65)) + "\n",
            "polish-template.csv",
            "text/csv",
        )
        upload = st.file_uploader("CSV : exactement Attr1 à Attr64", type="csv")
        if upload:
            try:
                import csv

                header = next(csv.reader(io.StringIO(upload.getvalue().decode("utf-8-sig"))))
                if len(header) != len(set(header)):
                    raise ValueError("Colonnes dupliquées dans le CSV")
                frame = pd.read_csv(upload)
                required = {f"Attr{i}" for i in range(1, 65)}
                if set(frame.columns) != required:
                    raise ValueError(
                        f"Colonnes manquantes : {sorted(required - set(frame.columns))}; inattendues : {sorted(set(frame.columns) - required)}"
                    )
                st.dataframe(frame.head(20), width="stretch")
                if st.button("Analyser les lignes", type="primary"):
                    rows = [
                        {"features": {k: None if pd.isna(v) else v for k, v in row.items()}}
                        for row in frame.to_dict("records")
                    ]
                    result = request(
                        "POST", "/predict/batch", {"task": "bankruptcy_full", "rows": rows}
                    )
                    if result:
                        st.session_state["full_batch"] = result
                        valid = [r for r in result["rows"] if r["status"] == "ok"]
                        if valid:
                            first = valid[0]["index"]
                            st.session_state["full_result"] = (rows[first], valid[0]["result"])
                if "full_batch" in st.session_state:
                    batch = st.session_state["full_batch"]
                    st.caption(
                        f"{batch['valid_rows']} ligne(s) valide(s) sur {len(batch['rows'])}. "
                        "Les lignes à corriger ne sont pas évaluées."
                    )
                    summary_rows = []
                    for row in batch["rows"]:
                        valid = row["status"] == "ok"
                        fields = ", ".join(
                            ".".join(str(part) for part in error["location"] if part != "features")
                            for error in row.get("errors", [])
                        )
                        summary_rows.append(
                            {
                                "Ligne CSV": row["index"] + 2,
                                "Résultat": "Valide" if valid else "À corriger",
                                "Probabilité de faillite": (
                                    f"{row['result']['probability']:.1%}" if valid else ""
                                ),
                                "Classe indicative": (
                                    row["result"]["indicative_grade"] if valid else ""
                                ),
                                "Correction requise": ""
                                if valid
                                else f"Nombre fini requis : {fields}",
                            }
                        )
                    st.dataframe(summary_rows, hide_index=True, width="stretch")
                    st.download_button(
                        "Exporter les résultats JSON",
                        __import__("json").dumps(st.session_state["full_batch"]),
                        "full-results.json",
                    )
            except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
                st.error(str(exc))
    elif method == "Formulaire complet":
        values = {}
        with st.form("full-manual"):
            for category in [
                "Liquidity and capital",
                "Profitability and coverage",
                "Activity and turnover",
            ]:
                category_labels = {
                    "Liquidity and capital": "Liquidité et structure financière",
                    "Profitability and coverage": "Rentabilité et couverture",
                    "Activity and turnover": "Activité et rotation",
                }
                with st.expander(
                    category_labels[category], expanded=category == "Liquidity and capital"
                ):
                    columns = st.columns(2)
                    for index, (feature, definition) in enumerate(
                        (k, v) for k, v in dictionary.items() if v["category"] == category
                    ):
                        values[feature] = columns[index % 2].number_input(
                            feature + " *",
                            value=None,
                            help=definition["definition"],
                            key="manual" + feature,
                            format="%.6f",
                        )
            submitted = st.form_submit_button("Analyser les 64 ratios", type="primary")
        if submitted:
            if len(values) != 64 or any(v is None or not np.isfinite(v) for v in values.values()):
                st.error("Les 64 champs sont obligatoires et doivent contenir des nombres finis.")
            else:
                payload = {"features": values}
    else:
        st.info(
            "Exemples documentés issus de l'entraînement UCI. Les noms décrivent le passif relatif, pas un niveau de risque prédit."
        )
        profiles = request("GET", "/demo-profiles") or []
        if profiles:
            index = st.selectbox(
                "Profil descriptif",
                range(len(profiles)),
                format_func=lambda i: profiles[i]["label"],
            )
            st.caption(profiles[index]["provenance"])
            st.dataframe(pd.DataFrame([profiles[index]["features"]]))
            if st.button("Exécuter le modèle sur cet exemple", type="primary"):
                payload = {"features": profiles[index]["features"]}
    if payload:
        result = request("POST", "/predict/bankruptcy/full", payload)
        if result:
            st.session_state["full_result"] = (payload, result)
    if "full_result" in st.session_state:
        inputs, result = st.session_state["full_result"]
        display_prediction(result)
        explanation = request("POST", "/explain/bankruptcy/full", inputs)
        display_shap(explanation)
        simple = {
            "sme_id": "COMPARAISON",
            "sector": "Non renseigné",
            "annual_revenue": 0.0,
            "debt_ratio": inputs["features"]["Attr2"],
            "current_ratio": inputs["features"]["Attr4"],
            "requested_amount": 1.0,
            "loan_term_months": 1,
            "past_defaults": 0,
        }
        if simple["debt_ratio"] >= 0 and simple["current_ratio"] >= 0:
            compared = request("POST", "/predict/sme", simple)
            if compared:
                st.metric(
                    "Modèle simplifié, mêmes Attr2 et Attr4",
                    f"{compared['prediction']['probability']:.1%}",
                )
                st.caption("Comparaison de deux modèles du même événement, sans moyenne ni fusion.")
        importance = request("GET", "/models/bankruptcy_full/global-importance")
        if importance:
            frame = (
                pd.DataFrame(
                    importance.items(), columns=["Variable", "Contribution moyenne absolue"]
                )
                .sort_values("Contribution moyenne absolue")
                .tail(15)
            )
            st.plotly_chart(
                px.bar(
                    frame,
                    x="Contribution moyenne absolue",
                    y="Variable",
                    orientation="h",
                    title="Importance globale SHAP",
                ),
                width="stretch",
            )
        report_download("/reports/bankruptcy/full.pdf", inputs, "analyse-financiere")

elif page == "Évaluation crédit avancée":
    title(
        "Évaluation crédit avancée",
        "Risque historique de charge-off d'un prêt aux conditions approuvées.",
    )
    st.warning(
        "Population SBA américaine de prêts historiquement approuvés et résolus. Horizon variable ; aucune validation comme décision avant accord."
    )
    submitted, inputs = credit_form()
    if submitted:
        result = request("POST", "/predict/credit", inputs)
        if result:
            st.session_state["credit_result"] = (inputs, result)
    if "credit_result" in st.session_state:
        inputs, result = st.session_state["credit_result"]
        display_prediction(result)
        display_shap(request("POST", "/explain/credit", inputs))
        st.caption(
            "La durée Term est exclue : sa définition contractuelle initiale n'a pas été établie."
        )
        changed_amount = st.number_input(
            "Scénario : nouveau montant approuvé (USD)",
            min_value=200.0,
            value=float(inputs["GrAppv"]),
        )
        if st.button("Comparer le scénario de montant"):
            changed = {
                **inputs,
                "GrAppv": changed_amount,
                "SBA_Appv": changed_amount * inputs["SBA_Appv"] / inputs["GrAppv"],
            }
            simulated = request("POST", "/predict/credit", changed)
            if simulated:
                st.metric(
                    "Probabilité du scénario",
                    f"{simulated['probability']:.1%}",
                    f"{(simulated['probability'] - result['probability']) * 100:+.2f} points",
                )
                st.caption(
                    "Garantie proportionnelle constante ; variation associée au modèle, sans interprétation causale."
                )
        report_download("/reports/credit.pdf", inputs, "credit-sba")

elif page == "Simulateur financier":
    title(
        "Simulateur financier",
        "Échéancier, coût du financement, sensibilité comptable et pertes sous hypothèses explicites.",
    )
    a, b, c = st.columns(3)
    amount = a.number_input("Capital simulé", min_value=1.0, value=100000.0)
    months = b.number_input("Durée (mois)", min_value=1, max_value=600, value=36)
    rate = c.slider("Taux annuel nominal (%)", 0.0, 50.0, 7.0, 0.25) / 100
    include_loss = st.checkbox(
        "Ajouter une PD de crédit annuelle hypothétique distincte des modèles de faillite"
    )
    payload = {"principal": amount, "months": months, "annual_rate": rate}
    if include_loss:
        a, b, c = st.columns(3)
        payload["assumed_annual_credit_pd"] = (
            a.slider("PD de crédit annuelle assumée (%)", 0.0, 100.0, 5.0) / 100
        )
        payload["assumed_lgd"] = b.slider("LGD assumée (%)", 0.0, 100.0, 45.0) / 100
        payload["assumed_ead"] = c.number_input("EAD assumée", min_value=0.0, value=amount)
    result = request("POST", "/simulate", payload)
    if result:
        a, b, c = st.columns(3)
        a.metric("Mensualité", f"{result['repayment']['monthly_payment']:,.2f}")
        b.metric("Coût du financement", f"{result['repayment']['financing_cost']:,.2f}")
        c.metric("Total remboursé", f"{result['repayment']['total_payments']:,.2f}")
        if include_loss:
            st.json(result["credit_loss_scenario"])
            st.json(result["pricing_scenario"])
        st.caption(result["interpretation"])
    st.subheader("Sensibilité financière et comptable")
    with st.form("accounting"):
        a, b, c = st.columns(3)
        assets = a.number_input("Actif total", min_value=1.0, value=200000.0)
        liabilities = b.number_input("Passif total", min_value=0.0, value=80000.0)
        equity = c.number_input("Capitaux propres", value=120000.0)
        revenue = a.number_input("Chiffre d'affaires du scénario", min_value=0.0, value=250000.0)
        debt = b.number_input("Dette financière", min_value=0.0, value=60000.0)
        ca = c.number_input("Actif courant", min_value=0.0, value=60000.0)
        cl = a.number_input("Dettes à court terme", min_value=1.0, value=30000.0)
        inventory = b.number_input("Stocks", min_value=0.0, value=10000.0)
        receivables = c.number_input("Créances d'exploitation", min_value=0.0, value=20000.0)
        payables = a.number_input("Dettes d'exploitation", min_value=0.0, value=15000.0)
        capital = b.number_input("Capitaux permanents", value=170000.0)
        fixed = c.number_input("Actifs immobilisés", min_value=0.0, value=140000.0)
        submitted = st.form_submit_button("Calculer et comparer le risque de faillite")
    if submitted:
        accounts = request(
            "POST",
            "/financial-analysis",
            {
                "total_assets": assets,
                "total_liabilities": liabilities,
                "financial_debt": debt,
                "equity": equity,
                "current_assets": ca,
                "current_liabilities": cl,
                "inventory": inventory,
                "operating_receivables": receivables,
                "operating_payables": payables,
                "long_term_capital": capital,
                "fixed_assets": fixed,
            },
        )
        if accounts:
            st.json(accounts)
        baseline = st.session_state.get(
            "sme_assessment",
            (
                {
                    "sme_id": "SCENARIO",
                    "sector": "Simulation",
                    "annual_revenue": revenue,
                    "debt_ratio": 0.42,
                    "current_ratio": 1.85,
                    "requested_amount": amount,
                    "loan_term_months": months,
                    "past_defaults": 0,
                },
                None,
            ),
        )[0]
        scenario = {
            **baseline,
            "annual_revenue": revenue,
            "debt_ratio": liabilities / assets,
            "current_ratio": ca / cl,
            "requested_amount": amount,
            "loan_term_months": months,
        }
        sensitivity = request(
            "POST", "/simulate", {**payload, "baseline_sme": baseline, "scenario_sme": scenario}
        )
        if sensitivity:
            a, b = st.columns(2)
            a.metric(
                "Faillite : situation initiale",
                f"{sensitivity['baseline_sme']['prediction']['probability']:.1%}",
            )
            b.metric(
                "Faillite : scénario",
                f"{sensitivity['scenario_sme']['prediction']['probability']:.1%}",
            )
            st.caption(
                "La probabilité ne varie qu'avec passif/actif et liquidité. Les autres montants modifient uniquement les calculs financiers."
            )

elif page == "Analyse de portefeuille":
    title(
        "Analyse de portefeuille", "Scoring batch, segmentation et exports par modèle et événement."
    )
    task = st.selectbox("Modèle", ["sme", "bankruptcy_full", "credit"])
    upload = st.file_uploader("Importer un CSV conforme au modèle sélectionné", type="csv")
    name = st.text_input("Nom du portefeuille", "Portefeuille de démonstration")
    persist = st.checkbox("Enregistrer explicitement les résultats dans PostgreSQL", value=False)
    if upload and st.button("Scorer le portefeuille", type="primary"):
        try:
            frame = pd.read_csv(upload)
            rows = [
                {k: None if pd.isna(v) else v for k, v in row.items()}
                for row in frame.to_dict("records")
            ]
            if task == "bankruptcy_full":
                rows = [{"features": row} for row in rows]
            result = request(
                "POST",
                "/predict/batch",
                {"task": task, "rows": rows, "persist": persist, "portfolio_name": name},
            )
            if result:
                st.session_state["portfolio_result"] = result
        except (ValueError, pd.errors.ParserError) as exc:
            st.error(str(exc))
    stored = request("GET", "/portfolios") or []
    if stored:
        selected = st.selectbox(
            "Portefeuille enregistré",
            stored,
            format_func=lambda p: f"{p['id']} - {p['name']} ({p['task']})",
        )
        if st.button("Charger les analyses"):
            result = request("GET", f"/portfolio/analytics?portfolio_id={selected['id']}")
            if result:
                st.session_state["portfolio_result"] = result
    if "portfolio_result" in st.session_state:
        result = st.session_state["portfolio_result"]
        records = []
        for row in result["rows"]:
            if row["status"] == "ok":
                records.append(
                    {
                        "index": row["index"],
                        "sector": row["sector"],
                        **row["result"].get("prediction", row["result"]),
                    }
                )
        if records:
            frame = pd.DataFrame(records)
            a, b = st.columns(2)
            a.plotly_chart(
                px.histogram(
                    frame, x="probability", nbins=20, title="Distribution du risque estimé"
                ),
                width="stretch",
            )
            b.plotly_chart(
                px.histogram(
                    frame, x="indicative_grade", color="sector", title="Segmentation par secteur"
                ),
                width="stretch",
            )
            threshold = st.slider("Seuil de signalement", 0.0, 1.0, 0.1, 0.01)
            st.metric("Dossiers au-dessus du seuil", int((frame.probability >= threshold).sum()))
            matrix = pd.crosstab(frame.sector, frame.indicative_grade).reindex(
                columns=list("ABCDEF"), fill_value=0
            )
            st.plotly_chart(
                px.imshow(matrix, text_auto=True, title="Matrice de segmentation sectorielle"),
                width="stretch",
            )
            st.dataframe(frame, width="stretch")
            st.download_button(
                "Exporter CSV", frame.to_csv(index=False), "portfolio-results.csv", "text/csv"
            )
            st.caption(
                "Les pertes de crédit ne sont pas déduites des probabilités de faillite. Utilisez des hypothèses explicites dans le simulateur."
            )
            with st.expander("Scénario de perte du portefeuille sous hypothèses de crédit"):
                st.caption(
                    "PD de crédit annuelle assumée, distincte des probabilités affichées. Une exposition identique par dossier est supposée."
                )
                a, b, c = st.columns(3)
                assumed_pd = (
                    a.slider("PD de crédit assumée (%)", 0.0, 100.0, 5.0, key="portfolio-pd") / 100
                )
                assumed_lgd = (
                    b.slider("LGD assumée (%)", 0.0, 100.0, 45.0, key="portfolio-lgd") / 100
                )
                ead_per_row = c.number_input(
                    "EAD assumée par dossier", min_value=0.0, value=100000.0
                )
                scenario = request(
                    "POST",
                    "/simulate",
                    {
                        "principal": max(1.0, ead_per_row * len(frame)),
                        "months": 12,
                        "annual_rate": 0.0,
                        "assumed_annual_credit_pd": assumed_pd,
                        "assumed_lgd": assumed_lgd,
                        "assumed_ead": ead_per_row * len(frame),
                    },
                )
                if scenario:
                    st.metric(
                        "Perte attendue simulée totale",
                        f"{scenario['credit_loss_scenario']['expected_loss']:,.2f}",
                    )
                    segments = frame.groupby("indicative_grade").size().reset_index(name="Dossiers")
                    segments["Perte simulée"] = (
                        segments.Dossiers * ead_per_row * assumed_pd * assumed_lgd
                    )
                    st.dataframe(segments, width="stretch")
                st.caption(
                    "EL = PD assumée × LGD assumée × EAD assumée. Aucun effet de causalité ni rendement bancaire observé."
                )
        invalid = [r for r in result["rows"] if r["status"] != "ok"]
        if invalid:
            st.warning(f"{len(invalid)} lignes invalides")
            st.json(invalid)

else:
    title(
        "Modèles & MLOps",
        "Versions indépendantes, évaluations, dérive des entrées et promotions contrôlées.",
    )
    info = request("GET", "/model-info")
    if info:
        for _task, model in info["models"].items():
            with st.expander(model["model_name"], expanded=True):
                if not model["available"]:
                    st.warning("Modèle indisponible")
                    continue
                st.caption(f"Champion v{model['version']} · {model['winner']} · {model['horizon']}")
                a, b, c = st.columns(3)
                measured = model["test"] if "roc_auc" in model["test"] else model["validation"]
                label = "test" if "roc_auc" in model["test"] else "qualification"
                a.metric(f"ROC-AUC {label}", f"{measured['roc_auc']:.3f}")
                b.metric(f"PR-AUC (AP) {label}", f"{measured['pr_auc_average_precision']:.3f}")
                c.metric(f"Brier {label}", f"{measured['brier']:.4f}")
                st.json({"validation": model["validation"], "test": model["test"]}, expanded=False)
        st.link_button(
            "Ouvrir MLflow local", os.environ.get("MLFLOW_PUBLIC_URL", "http://localhost:5001")
        )
    with st.expander("Versions enregistrées dans MLflow"):
        if st.button("Charger le registre"):
            versions = request("GET", "/management/registry")
            if versions:
                st.dataframe(pd.DataFrame(versions), width="stretch")
    reports = request("GET", "/management/reports")
    if reports:
        st.json(reports, expanded=False)
    st.info(
        "La dérive des entrées recommande une investigation ; elle ne prouve pas une baisse de performance et ne promeut jamais un modèle."
    )
    with st.expander("Promotion et rollback - administrateur"):
        token = st.text_input("Secret administrateur", type="password")
        task = st.selectbox("Modèle à gérer", ["sme", "bankruptcy_full", "credit"])
        path = st.text_input("Chemin relatif du candidat enregistré", "artifacts/")
        reason = st.text_input("Motif auditable", "Validation manuelle du candidat")
        a, b = st.columns(2)
        if a.button("Promouvoir le candidat"):
            result = request(
                "POST",
                "/management/promote",
                {"task": task, "candidate_path": path, "reason": reason},
                token=token,
            )
            if result:
                st.success("Promotion appliquée ; modèles rechargés.")
        if b.button("Restaurer le champion précédent"):
            result = request(
                "POST", "/management/rollback", {"task": task, "reason": reason}, token=token
            )
            if result:
                st.success("Rollback appliqué.")
    st.code(
        "fintech drift --task sme --current data/current/sme.csv\nfintech retrain --task sme --trials 10",
        language="powershell",
    )
