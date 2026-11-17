from copy import deepcopy
from datetime import date

import pytest

from fintech_risk.dependency_audit import evaluate_audit

TODAY = date(2026, 11, 17)
POLICY = {
    "schema_version": 1,
    "exceptions": [
        {
            "package": "diskcache",
            "version": "5.6.3",
            "advisory": "PYSEC-2026-2447",
            "expires": "2026-12-17",
            "owner": "Test maintainer",
            "reason": "Test policy",
        }
    ],
}


def report(name="diskcache", version="5.6.3", advisory="PYSEC-2026-2447", fixes=None):
    return {
        "dependencies": [
            {
                "name": name,
                "version": version,
                "vulns": [{"id": advisory, "fix_versions": fixes or []}],
            }
        ]
    }


def test_exact_diskcache_risk_remains_visible():
    decision = evaluate_audit(report(), POLICY, TODAY)
    assert decision["status"] == "pass_with_exception"
    assert decision["accepted_risks"][0]["advisory"] == "PYSEC-2026-2447"


@pytest.mark.parametrize(
    "payload",
    [
        report(name="setuptools", version="79.0.1"),
        report(version="5.6.2"),
        report(advisory="A-NEW-DISKCACHE-ADVISORY"),
        report(fixes=["5.6.4"]),
    ],
)
def test_other_packages_versions_advisories_or_available_fix_block(payload):
    assert evaluate_audit(payload, POLICY, TODAY)["status"] == "blocked"


def test_additional_finding_is_never_hidden_by_accepted_diskcache_risk():
    payload = report()
    payload["dependencies"] += report("setuptools", "79.0.1", "GHSA-xmj3-9gf7-h52w")["dependencies"]
    decision = evaluate_audit(payload, POLICY, TODAY)
    assert len(decision["accepted_risks"]) == 1
    assert decision["blocked_findings"][0]["package"] == "setuptools"


def test_expiry_requires_review_even_if_report_is_clean():
    with pytest.raises(ValueError, match="expired"):
        evaluate_audit({"dependencies": []}, POLICY, date(2026, 12, 17))


def test_no_policy_is_a_strict_gate():
    assert (
        evaluate_audit(report(), {"schema_version": 1, "exceptions": []}, TODAY)["status"]
        == "blocked"
    )


def test_malformed_report_fails_closed():
    with pytest.raises(ValueError):
        evaluate_audit({}, POLICY, TODAY)
    invalid = deepcopy(POLICY)
    invalid["exceptions"][0]["expires"] = "never"
    with pytest.raises(ValueError):
        evaluate_audit(report(), invalid, TODAY)
