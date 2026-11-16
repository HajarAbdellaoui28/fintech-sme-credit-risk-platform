"""Readable paginated PDF reports with explicit probability and financial semantics."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def assessment_pdf(title, result):
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
        title=title,
    )
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#142740")
    flow = [
        Paragraph("FinSight | " + escape(title), styles["Title"]),
        Spacer(1, 0.35 * cm),
        Paragraph(
            "Prototype académique d'aide à l'analyse. Aucune décision de prêt automatique. Aucune conformité Bâle certifiée.",
            styles["BodyText"],
        ),
    ]
    prediction = result.get("prediction", result)
    labels = [
        (
            "Événement",
            "Faillite de l'entreprise"
            if prediction["predicted_event"] == "corporate_bankruptcy"
            else "Charge-off du prêt",
        ),
        (
            "Horizon",
            "Un an"
            if prediction["horizon"] == "1_year"
            else "Issue historique du prêt, horizon variable",
        ),
        ("Probabilité estimée", f"{prediction['probability']:.2%}"),
        ("Classe indicative", prediction["indicative_grade"]),
        ("Modèle", prediction["model_name"]),
        ("Version", prediction["model_version"]),
    ]
    rows = [
        [Paragraph(str(a), styles["BodyText"]), Paragraph(escape(str(b)), styles["BodyText"])]
        for a, b in labels
    ]
    table = Table(rows, colWidths=[5.1 * cm, 12.2 * cm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e1eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    flow.extend([Spacer(1, 0.4 * cm), table, Spacer(1, 0.4 * cm)])
    for warning in prediction["warnings"]:
        flow.append(Paragraph(escape(warning), styles["BodyText"]))
    if "financial_analysis" in result:
        analysis = result["financial_analysis"]
        flow.extend(
            [
                Spacer(1, 0.3 * cm),
                Paragraph("Analyse financière distincte du modèle", styles["Heading2"]),
            ]
        )
        for key in [
            "sme_id",
            "sector",
            "financing_to_revenue",
            "liabilities_to_assets",
            "current_ratio",
        ]:
            value = analysis[key]
            label = {
                "sme_id": "Référence du dossier",
                "sector": "Secteur",
                "financing_to_revenue": "Financement / chiffre d'affaires",
                "liabilities_to_assets": "Passif total / actif total",
                "current_ratio": "Liquidité générale",
            }[key]
            if isinstance(value, dict):
                value = (
                    value.get("value") if value.get("value") is not None else value.get("reason")
                )
            if isinstance(value, (float, int)):
                value = f"{value:.1%}" if key == "financing_to_revenue" else f"{value:.3f}"
            flow.append(Paragraph(escape(f"{label} : {value}"), styles["BodyText"]))
        for alert in analysis["alerts"]:
            flow.append(Paragraph(escape(alert), styles["BodyText"]))
        simulation = analysis["loan_repayment_simulation"]
        flow.append(
            Paragraph(
                f"Financement hypothétique : taux nominal annuel fixe de {simulation['assumptions']['annual_nominal_rate']:.1%}, frais nuls. "
                f"Mensualité : {simulation['monthly_payment']:,.2f} ; "
                f"coût total du financement : {simulation['financing_cost']:,.2f}. "
                "Cette hypothèse ne dépend pas de la probabilité de faillite.",
                styles["BodyText"],
            )
        )
        flow.append(
            Paragraph(escape(analysis["expected_credit_loss"]["reason"]), styles["BodyText"])
        )
    if "explanation" in result:
        explanation = result["explanation"]
        flow.extend(
            [
                Spacer(1, 0.3 * cm),
                Paragraph("Contributions locales SHAP", styles["Heading2"]),
                Paragraph(
                    escape(explanation["scale"] + ". " + explanation["calibration_note"]),
                    styles["BodyText"],
                ),
            ]
        )
        pairs = sorted(
            zip(explanation["feature_names"], explanation["values"][0], strict=True),
            key=lambda p: abs(p[1]),
            reverse=True,
        )[:12]
        for name, value in pairs:
            flow.append(Paragraph(escape(f"{name} : {value:+.5f}"), styles["BodyText"]))
        flow.append(
            Paragraph(
                "Contributions associatives, sans interprétation causale.", styles["BodyText"]
            )
        )
    flow.extend(
        [
            Spacer(1, 0.4 * cm),
            Paragraph("Hypothèses et limites", styles["Heading2"]),
            Paragraph(
                "La probabilité de faillite n'est pas une PD de crédit. LGD, EAD, taux d'intérêt et pertes attendues nécessitent des hypothèses indépendantes explicites. Les résultats historiques ne garantissent aucune performance future.",
                styles["BodyText"],
            ),
        ]
    )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#68788e"))
        canvas.drawString(
            1.7 * cm, 1 * cm, "FinSight - Données déclarées et modèles historiques - Confidentiel"
        )
        canvas.drawRightString(19.3 * cm, 1 * cm, f"Page {doc.page}")

    document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
