"""Documented feature contracts; no fabricated accounting mappings."""

POLISH_DEFINITIONS = [
    "Net profit / total assets",
    "Total liabilities / total assets",
    "Working capital / total assets",
    "Current assets / short-term liabilities",
    "[(Cash + short-term securities + receivables - short-term liabilities) / (operating expenses - depreciation)] * 365",
    "Retained earnings / total assets",
    "EBIT / total assets",
    "Book value of equity / total liabilities",
    "Sales / total assets",
    "Equity / total assets",
    "(Gross profit + extraordinary items + financial expenses) / total assets",
    "Gross profit / short-term liabilities",
    "(Gross profit + depreciation) / sales",
    "(Gross profit + interest) / total assets",
    "(Total liabilities * 365) / (gross profit + depreciation)",
    "(Gross profit + depreciation) / total liabilities",
    "Total assets / total liabilities",
    "Gross profit / total assets",
    "Gross profit / sales",
    "(Inventory * 365) / sales",
    "Sales (n) / sales (n-1)",
    "Profit on operating activities / total assets",
    "Net profit / sales",
    "Gross profit (in 3 years) / total assets",
    "(Equity - share capital) / total assets",
    "(Net profit + depreciation) / total liabilities",
    "Profit on operating activities / financial expenses",
    "Working capital / fixed assets",
    "Logarithm of total assets",
    "(Total liabilities - cash) / sales",
    "(Gross profit + interest) / sales",
    "(Current liabilities * 365) / cost of products sold",
    "Operating expenses / short-term liabilities",
    "Operating expenses / total liabilities",
    "Profit on sales / total assets",
    "Total sales / total assets",
    "(Current assets - inventories) / long-term liabilities",
    "Constant capital / total assets",
    "Profit on sales / sales",
    "(Current assets - inventory - receivables) / short-term liabilities",
    "Total liabilities / ((profit on operating activities + depreciation) * (12/365))",
    "Profit on operating activities / sales",
    "Receivables rotation + inventory turnover in days",
    "(Receivables * 365) / sales",
    "Net profit / inventory",
    "(Current assets - inventory) / short-term liabilities",
    "(Inventory * 365) / cost of products sold",
    "EBITDA (profit on operating activities - depreciation) / total assets [UCI wording]",
    "EBITDA (profit on operating activities - depreciation) / sales [UCI wording]",
    "Current assets / total liabilities",
    "Short-term liabilities / total assets",
    "(Short-term liabilities * 365) / cost of products sold",
    "Equity / fixed assets",
    "Constant capital / fixed assets",
    "Working capital",
    "(Sales - cost of products sold) / sales",
    "(Current assets - inventory - short-term liabilities) / (sales - gross profit - depreciation)",
    "Total costs / total sales",
    "Long-term liabilities / equity",
    "Sales / inventory",
    "Sales / receivables",
    "(Short-term liabilities * 365) / sales",
    "Sales / short-term liabilities",
    "Sales / fixed assets",
]
POLISH_FEATURES = [f"Attr{i}" for i in range(1, 65)]
SIMPLIFIED_FEATURES = ["Attr2", "Attr4"]
CREDIT_NUMERIC = ["GrAppv", "SBA_Appv", "guarantee_ratio", "NoEmp"]
CREDIT_CATEGORICAL = ["NAICS2", "NewExist", "State", "UrbanRural", "LowDoc", "RevLineCr"]
CREDIT_FEATURES = CREDIT_NUMERIC + CREDIT_CATEGORICAL
FORBIDDEN_CREDIT = {
    "MIS_Status",
    "ChgOffDate",
    "ChgOffPrinGr",
    "BalanceGross",
    "DisbursementDate",
    "DisbursementGross",
    "Name",
    "LoanNr_ChkDgt",
    "Term",
    "CreateJob",
    "RetainedJob",
}


def polish_dictionary():
    return {
        name: {
            "definition": definition,
            "source": "UCI dataset 365, original order X1..X64",
            "category": "Liquidity and capital"
            if i in {2, 3, 4, 8, 10, 17, 28, 37, 38, 40, 46, 50, 51, 53, 54, 55, 59}
            else "Activity and turnover"
            if i in {9, 20, 21, 29, 32, 36, 43, 44, 47, 52, 60, 61, 62, 63, 64}
            else "Profitability and coverage",
        }
        for i, (name, definition) in enumerate(
            zip(POLISH_FEATURES, POLISH_DEFINITIONS, strict=True), 1
        )
    }
