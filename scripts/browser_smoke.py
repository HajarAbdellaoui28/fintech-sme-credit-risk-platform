"""Headless browser verification of real form scoring, CSV errors, exports and layout."""

import csv
import json
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

from fintech_risk.config import ROOT, save_json

output = ROOT / "reports/generated/screenshots"
output.mkdir(parents=True, exist_ok=True)
temporary = ROOT / "tmp/browser"
temporary.mkdir(parents=True, exist_ok=True)
features = httpx.get("http://127.0.0.1:8000/demo-profiles", timeout=20).json()[0]["features"]
file = temporary / "two-polish-profiles.csv"
with file.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=[f"Attr{i}" for i in range(1, 65)])
    writer.writeheader()
    writer.writerow(features)
    writer.writerow({**features, "Attr64": "invalid"})
browser_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
checks = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=str(browser_path), headless=True, args=["--disable-gpu"]
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1080}, accept_downloads=True)
    page = context.new_page()
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded", timeout=60000)
    page.get_by_role("button", name="Analyser le risque PME", exact=True).wait_for(timeout=60000)
    expect(page.locator('[data-testid="stForm"] input')).to_have_count(8, timeout=30000)
    page.get_by_role("button", name="Analyser le risque PME", exact=True).click()
    page.get_by_text("Probabilité estimée", exact=True).wait_for(timeout=60000)
    page.get_by_role("button", name="Préparer le rapport PDF", exact=True).wait_for(timeout=60000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=60000)
    page.screenshot(path=str(output / "01-main-assessment.png"), full_page=True)
    checks.append("eight_field_form_real_prediction")
    page.get_by_text("Analyse financière avancée", exact=True).first.click()
    page.get_by_text("CSV : exactement Attr1 à Attr64", exact=True).wait_for(timeout=60000)
    page.locator('input[type="file"]').set_input_files(str(file))
    page.get_by_role("button", name="Analyser les lignes", exact=True).wait_for(timeout=30000)
    page.get_by_role("button", name="Analyser les lignes", exact=True).click()
    page.get_by_role("button", name="Exporter les résultats JSON", exact=True).wait_for(
        timeout=60000
    )
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Exporter les résultats JSON", exact=True).click()
    exported = temporary / "csv-results.json"
    download_info.value.save_as(str(exported))
    data = json.loads(exported.read_text(encoding="utf-8"))
    assert data["valid_rows"] == 1 and data["rows"][1]["status"] == "invalid"
    page.get_by_text("Probabilité estimée", exact=True).wait_for(timeout=60000)
    page.get_by_role("button", name="Préparer le rapport PDF", exact=True).wait_for(timeout=60000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=60000)
    page.locator('[data-testid="stMain"]').evaluate("element => element.scrollTop = 0")
    page.screenshot(path=str(output / "02-full-csv-analysis.png"), full_page=True)
    checks.append("csv_real_prediction_row_error_and_download")
    mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
    mobile = mobile_context.new_page()
    mobile.goto("http://127.0.0.1:8501", wait_until="domcontentloaded", timeout=60000)
    mobile.get_by_role("button", name="Analyser le risque PME", exact=True).wait_for(timeout=60000)
    expect(mobile.locator('[data-testid="stForm"] input')).to_have_count(8, timeout=30000)
    mobile.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=60000)
    mobile.screenshot(path=str(output / "03-mobile-assessment.png"), full_page=True)
    assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 5")
    checks.append("mobile_no_horizontal_overflow")
    assert page.locator('[data-testid="stException"]').count() == 0
    browser.close()
save_json(
    ROOT / "reports/generated/browser_checks.json",
    {
        "executed": True,
        "checks": checks,
        "browser": "isolated headless Chrome",
        "screenshots": str(output.relative_to(ROOT)),
    },
)
print("Browser checks passed:", len(checks))
