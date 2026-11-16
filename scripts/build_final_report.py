"""Generate French engineering and financial PDF reports from actual execution evidence."""

from xml.sax.saxutils import escape

from defusedxml import ElementTree
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from fintech_risk.config import ROOT, read_json

output = ROOT / "output/pdf"
output.mkdir(parents=True, exist_ok=True)
for evidence_name in [
    "live_integration.json",
    "dashboard_behavior.json",
    "browser_checks.json",
    "model_delivery_verification.json",
    "drift_verification.json",
    "docker_verification.json",
    "training_image_verification.json",
    "preprocessing_parity.json",
    "reproducibility.json",
]:
    assert read_json(ROOT / "reports/generated" / evidence_name)["executed"] is True
assert read_json(ROOT / "reports/generated/latency.json")["completed"] is True
manifest = read_json(ROOT / "artifacts/deployment.json")
models = {task: read_json(ROOT / ref["path"] / "metadata.json") for task, ref in manifest.items()}
styles = getSampleStyleSheet()
styles["Title"].textColor = colors.HexColor("#142740")
styles["Heading1"].textColor = colors.HexColor("#137c78")
styles["BodyText"].spaceAfter = 7
styles["BodyText"].leading = 14


def paragraph(text, style="BodyText"):
    return Paragraph(escape(str(text)), styles[style])


def table(rows, widths=None):
    elements = [[paragraph(cell) for cell in row] for row in rows]
    obj = Table(elements, colWidths=widths, repeatRows=1, hAlign="LEFT")
    obj.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f1f0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dce4ee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return obj


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#69788d"))
    canvas.drawString(
        1.6 * cm, 1 * cm, "FinSight | Rapport d'ingénierie académique | Données historiques"
    )
    canvas.drawRightString(19.4 * cm, 1 * cm, f"Page {doc.page}")


def render(path, flow):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=(21 * cm, 29.7 * cm),
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.6 * cm,
    )
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)


names = {
    "sme": "Faillite simplifiée",
    "bankruptcy_full": "Faillite complète",
    "credit": "Charge-off SBA",
}
metric_rows = [["Modèle", "ROC-AUC", "AP", "Brier", "Test"]]
for task in ["sme", "bankruptcy_full", "credit"]:
    m = models[task]
    test = m["test"]
    metric_rows.append(
        [
            names[task],
            f"{test['roc_auc']:.4f}",
            f"{test['pr_auc_average_precision']:.4f}",
            f"{test['brier']:.5f}",
            str(test["rows"]),
        ]
    )

flow = [
    paragraph("FinSight", "Title"),
    paragraph("Plateforme FinTech SME Credit Risk Analytics", "Heading1"),
    paragraph("Rapport final d'architecture, d'évaluation et de vérification locale"),
    paragraph(
        "Prototype académique d'aide à l'analyse. Les probabilités de faillite et de charge-off restent indépendantes ; aucune conformité Bâle ni décision bancaire automatique n'est revendiquée."
    ),
    paragraph("1. Architecture livrée", "Heading1"),
    paragraph(
        "Données brutes immuables -> validation et préparation PySpark -> trois pipelines indépendants -> MLflow et manifeste approuvé -> FastAPI -> six sections Streamlit. PostgreSQL persiste les portefeuilles, dossiers volontairement enregistrés et événements de gestion. DVC assure le versionnement ; Evidently compare les entrées."
    ),
    paragraph(
        "Le formulaire principal comporte exactement huit champs. Seuls passif total / actif total (Attr2) et liquidité générale (Attr4) alimentent son modèle ML réel. Les six autres champs servent aux ratios, alertes, références et simulations."
    ),
    paragraph("2. Résultats empiriques finaux", "Heading1"),
    table(metric_rows, [6 * cm, 2.8 * cm, 2.6 * cm, 2.8 * cm, 3.6 * cm]),
    Spacer(1, 0.3 * cm),
    paragraph(
        "AP désigne l'average precision. Les deux modèles Polish partagent exactement les mêmes 1 170 observations de test. Le score SBA porte sur un horizon historique variable et ne constitue pas une PD annuelle."
    ),
    paragraph(
        "Les 64 variables améliorent nettement la discrimination sur ce test historique. Le modèle simplifié reste limité. Le modèle SBA présente une calibration insuffisante sous changement temporel de population ; son Brier ne justifie pas un usage bancaire de sa probabilité."
    ),
]

flow += [
    PageBreak(),
    paragraph("3. Données et intégrité ML", "Heading1"),
    table(
        [
            ["Population", "Entraînement", "Validation", "Test"],
            ["Polish, un an", "3 510", "1 170", "1 170"],
            ["SBA admissible", "527 575", "174 223", "178 670"],
        ],
        [6.3 * cm, 3.8 * cm, 3.8 * cm, 3.9 * cm],
    ),
    Spacer(1, 0.3 * cm),
    paragraph(
        "Les 899 164 lignes SBA contiennent 739 609 PIF, 157 558 CHGOFF et 1 997 cibles absentes. La cohorte principale exclut les cibles absentes, les PIF avec date de charge-off et les emprunteurs communs aux partitions antérieures. Le découpage est chronologique."
    ),
    paragraph(
        "Polish 5year.arff correspond à une faillite à un an : 5 910 lignes initiales et 410 positifs ; après déduplication, 5 850 profils et 408 positifs. Les quatre autres cohortes sont auditées mais jamais regroupées avec cet horizon."
    ),
    paragraph(
        "Chaque tâche compare Logistic Regression, Random Forest et XGBoost. Optuna règle les hyperparamètres sur des plis internes ; calibration sur prédictions hors pli d'entraînement ; sélection et seuils sur validation. Les ajustements finaux utilisent toutes les lignes admissibles d'entraînement ; le réglage SBA est plafonné à 100 000 lignes tracées."
    ),
    paragraph(
        "Des références Logistic Regression et Random Forest MLlib ont été réellement exécutées pour les trois tâches. Leur aire PR n'est pas confondue avec l'average precision scikit-learn."
    ),
    paragraph("Limites méthodologiques", "Heading2"),
    paragraph(
        "SBA : prêts approuvés et résolus, censure non corrigible complètement, date d'extraction non certifiée, forte variation de prévalence. Term est exclu faute de preuve de sa disponibilité contractuelle originale. GrAppv ne remplace jamais un montant demandé."
    ),
    paragraph(
        "Polish : pas d'identifiant de firme ni de calendrier exploitable ; unités et conventions de certains agrégats non établies. Attr24 ne précise pas explicitement la temporalité de ses trois années : l'absence totale de fuite temporelle du modèle complet ne peut être certifiée. Le modèle simplifié n'utilise pas Attr24."
    ),
    paragraph(
        "SHAP explique les contributions du modèle de base, avant la transformation de calibration ; aucune interprétation causale n'est présentée."
    ),
]

live = ROOT / "reports/generated/live_integration.json"
ui = ROOT / "reports/generated/dashboard_behavior.json"
browser = ROOT / "reports/generated/browser_checks.json"
delivery = ROOT / "reports/generated/model_delivery_verification.json"
drift = ROOT / "reports/generated/drift_verification.json"
docker = ROOT / "reports/generated/docker_verification.json"
repro = ROOT / "reports/generated/reproducibility.json"
tests = ROOT / "reports/generated/tests-final.xml"
verification_rows = [["Périmètre", "Preuve et état"]]
for label, path, key in [
    ("API et PostgreSQL", live, "checks"),
    ("Six sections Streamlit", ui, "checks"),
    ("Navigateur, CSV et mobile", browser, "checks"),
]:
    if path.exists():
        verification_rows.append(
            [label, f"Exécuté : {len(read_json(path)[key])} contrôles réussis"]
        )
    else:
        verification_rows.append([label, "Non vérifié dans ce rapport"])
for label, path in [
    ("Promotion et rollback protégés", delivery),
    ("Evidently : témoin et perturbation", drift),
    ("Docker Compose", docker),
    ("Reproduction DVC", repro),
]:
    verification_rows.append(
        [
            label,
            "Exécuté, preuve JSON disponible" if path.exists() else "Non vérifié dans ce rapport",
        ]
    )
if tests.exists():
    suite = ElementTree.parse(tests).getroot()
    counts = [s.attrib for s in suite.iter("testsuite")]
    verification_rows.append(
        [
            "Pytest",
            f"{sum(int(s.get('tests', 0)) for s in counts)} tests ; {sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in counts)} échec(s)",
        ]
    )
flow += [
    PageBreak(),
    paragraph("4. Fonctionnalités et preuves d'exécution", "Heading1"),
    table(verification_rows, [7 * cm, 10.8 * cm]),
    Spacer(1, 0.3 * cm),
    paragraph(
        "L'analyse complète propose un CSV strict de 64 variables avec erreurs par ligne, un formulaire manuel documenté et trois profils descriptifs issus de l'entraînement. Les exemples ne sont pas nommés selon un risque supposé avant exécution."
    ),
    paragraph(
        "Le simulateur sépare recalculs réellement supportés par les modèles et règles financières. Le portefeuille propose scoring batch, répartition sectorielle, classes indicatives, sensibilité des seuils et exports. Les PDF exposent événement, horizon, version, contributions et hypothèses."
    ),
    paragraph(
        "Les contrôles de promotion exigent un secret administrateur et des métriques de qualification admissibles. Une promotion réelle du candidat simplifié et un rollback ont été exécutés ; les champions initiaux ont été restaurés. Le test final du candidat de réentraînement est resté fermé."
    ),
    paragraph(
        "La démonstration de dérive utilise des témoins identiques et des perturbations volontairement étiquetées. Elle ne représente ni une dérive de production observée ni une baisse de performance. Aucun modèle n'est promu sur la seule dérive."
    ),
]

flow += [PageBreak(), paragraph("5. Latence, sécurité et CI/CD", "Heading1")]
latency = ROOT / "reports/generated/latency.json"
if latency.exists():
    measured = read_json(latency)
    rows = [["Modèle", "Modèle seul p95", "API p95, c=1", "API p95, c=4"]]
    for task in ["sme", "bankruptcy_full", "credit"]:
        item = measured["tasks"][task]
        rows.append(
            [
                names[task],
                f"{item['model_only']['p95_ms']:.2f} ms",
                f"{item['api']['1']['p95_ms']:.2f} ms",
                f"{item['api']['4']['p95_ms']:.2f} ms",
            ]
        )
    flow += [
        table(rows, [5.7 * cm, 4 * cm, 4 * cm, 4.1 * cm]),
        Spacer(1, 0.3 * cm),
        paragraph(
            "Mesures à chaud sur HTTP local avec connexion persistante, 1 000 requêtes par cas. La route SME comprend SHAP mis en cache ; les routes avancées excluent SHAP de la prédiction rapide. La cible de 100 ms est un résultat à vérifier par scénario, sans garantie de service ni revendication de latence à froid."
        ),
    ]
else:
    flow.append(
        paragraph(
            "Benchmark non exécuté dans cette version du rapport ; aucune latence n'est inventée."
        )
    )
flow += [
    paragraph("Sécurité", "Heading2"),
    paragraph(
        "Secrets hors Git, ports loopback, artefacts locaux de confiance vérifiés par empreinte, schémas stricts, calculs finis et logs sans charges utiles financières. Arrow, Spark et setuptools ont été mis à jour après audit. Bandit ne signale pas de problème moyen/élevé dans le périmètre contrôlé."
    ),
    paragraph(
        "Reste ouvert : PYSEC-2026-2447 sur DiskCache 5.6.3, sans correctif proposé. Le contrôle strict des dépendances n'est pas désactivé et reste en échec. Le cache doit rester privé et de confiance. Les tests fonctionnels réussis ne constituent pas une homologation de sécurité."
    ),
    paragraph("GitHub Actions", "Heading2"),
    paragraph(
        "CI, livraison d'images et livraison de modèles sont configurées. Lint, tests, contrôles de sécurité et builds ont des équivalents exécutés localement. Aucune exécution GitHub distante, publication de registre ou livraison cloud n'a été effectuée. Les environnements protégés, secrets et runner de formation nécessitent une configuration opérateur."
    ),
    paragraph("Exploitation locale", "Heading2"),
    paragraph(
        "docker compose up -d\nInterface : http://localhost:8501\nAPI : http://localhost:8000/docs\nMLflow : http://localhost:5001"
    ),
    paragraph(
        "Le profil training est séparé du démarrage applicatif. Les charges lourdes s'exécutent successivement. Le remote DVC local préserve les versions mais ne protège pas d'une perte du même disque."
    ),
]
render(output / "rapport_final.pdf", flow)

risk = [
    paragraph("Matrice de risque et simulations financières", "Title"),
    paragraph(
        "Hypothèses pédagogiques explicites, sans politique bancaire observée ni conformité réglementaire."
    ),
    paragraph("1. Matrice de coût normalisée", "Heading1"),
    table(
        [
            ["Issue observée / signalement", "Risque non signalé", "Risque signalé"],
            ["Événement absent", "TN : coût 0", "FP : coût 1"],
            ["Événement présent", "FN : coût 10", "TP : coût 0"],
        ],
        [7.3 * cm, 5.2 * cm, 5.3 * cm],
    ),
    Spacer(1, 0.3 * cm),
    paragraph(
        "Les seuils minimisent cette matrice sur validation uniquement. Les coûts sont hypothétiques et configurables dans params.yaml ; ils ne démontrent pas un rendement bancaire observé."
    ),
    paragraph("2. Seuils et résultats de test", "Heading1"),
]
rows = [["Modèle", "Seuil", "TN / FP / FN / TP", "Coût moyen simulé"]]
for task in ["sme", "bankruptcy_full", "credit"]:
    m = models[task]
    rows.append(
        [
            names[task],
            f"{m['threshold']:.4f}",
            str(m["test"]["confusion_matrix_tn_fp_fn_tp"]),
            f"{m['test']['simulated_cost']:.4f}",
        ]
    )
risk += [
    table(rows, [4.5 * cm, 2.2 * cm, 7.4 * cm, 3.7 * cm]),
    Spacer(1, 0.3 * cm),
    paragraph("3. Pertes et financement", "Heading1"),
    paragraph(
        "EL = PD de crédit × LGD × EAD. Exemple entièrement assumé : PD annuelle de crédit 5 %, LGD 45 %, EAD 100 000 unités -> EL 2 250 unités sur un an. La probabilité de faillite des modèles Polish n'est jamais substituée à cette PD."
    ),
    paragraph(
        "Taux annuel simulé = taux de base + marge de fonctionnement + PD annuelle de crédit assumée × LGD assumée. Aucune annualisation du score SBA à horizon variable n'est effectuée. Les échéanciers supposent un taux nominal fixe, des échéances mensuelles constantes et des frais nuls."
    ),
    paragraph("4. Sensibilité et limites", "Heading1"),
    paragraph(
        "Les grades A-F utilisent des bornes indicatives de 2 %, 5 %, 10 %, 20 % et 35 %. Modifier montant, durée ou chiffre d'affaires ne change pas le modèle simplifié ; seuls Attr2 et Attr4 le modifient. Les scénarios SBA utilisent des montants approuvés, sans substitution du montant demandé."
    ),
    paragraph(
        "Les probabilités concernent des événements et horizons distincts : elles ne sont ni additionnées ni moyennées. Les pertes ne sont pas cumulées deux fois sur la même exposition. La calibration SBA insuffisante limite l'interprétation de ses probabilités et exige une revue humaine."
    ),
]
render(output / "risk_matrix_report.pdf", risk)
print("French engineering and risk reports generated from execution artifacts.")
