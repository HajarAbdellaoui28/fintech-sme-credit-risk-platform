"""Keep the complete pip-audit report; gate only exact, expiring risk exceptions."""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def evaluate_audit(report, policy, today=None):
    today = today or datetime.now(timezone.utc).date()
    if policy.get("schema_version") != 1 or not isinstance(policy.get("exceptions"), list):
        raise ValueError("Invalid dependency audit policy")
    exceptions = {}
    for item in policy["exceptions"]:
        key = (item["package"], item["version"], item["advisory"])
        if not all(isinstance(part, str) and part for part in key):
            raise ValueError("Exception package, version and advisory must be explicit")
        if key in exceptions or not item.get("reason") or not item.get("owner"):
            raise ValueError("Duplicate or undocumented risk exception")
        if today >= date.fromisoformat(item["expires"]):
            raise ValueError(f"Risk exception expired: {key}")
        exceptions[key] = item
    if not isinstance(report.get("dependencies"), list):
        raise ValueError("Missing pip-audit dependency records")
    accepted, blocked, skipped = [], [], []
    for dependency in report["dependencies"]:
        if dependency.get("skip_reason"):
            skipped.append({"package": dependency["name"], "reason": dependency["skip_reason"]})
        elif not isinstance(dependency.get("vulns"), list):
            raise ValueError("Missing vulnerability list in dependency record")
        for issue in dependency.get("vulns", []):
            key = (dependency["name"], dependency["version"], issue["id"])
            finding = {
                "package": key[0],
                "version": key[1],
                "advisory": key[2],
                "fix_versions": issue["fix_versions"],
            }
            if not isinstance(finding["fix_versions"], list):
                raise ValueError("Invalid fix version list")
            # A newly available fix invalidates the exception and requires upgrading.
            if key in exceptions and not finding["fix_versions"]:
                accepted.append({**finding, "expires": exceptions[key]["expires"]})
            else:
                blocked.append(finding)
    return {
        "date_utc": today.isoformat(),
        "status": "blocked" if blocked else "pass_with_exception" if accepted else "pass",
        "accepted_risks": accepted,
        "blocked_findings": blocked,
        "skipped_dependencies": skipped,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("configs/dependency-audit-policy.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/generated/ci-security-audit.json")
    )
    parser.add_argument("--strict", action="store_true", help="Apply no risk exceptions")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    target = args.output.with_name(args.output.stem + ".decision.json")
    # Remove only our exact previous report, so a failed invocation cannot reuse it.
    args.output.unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--skip-editable",
            "--format",
            "json",
            "--output",
            str(args.output),
        ],
        check=False,
    )
    try:
        if result.returncode not in (0, 1):
            raise ValueError(f"pip-audit failed with exit code {result.returncode}")
        report = json.loads(args.output.read_text(encoding="utf-8"))
        policy = (
            {"schema_version": 1, "exceptions": []}
            if args.strict
            else json.loads(args.policy.read_text(encoding="utf-8"))
        )
        decision = evaluate_audit(report, policy)
        count = len(decision["accepted_risks"]) + len(decision["blocked_findings"])
        if (result.returncode == 1) != bool(count):
            raise ValueError("pip-audit exit status and vulnerability report disagree")
        decision["raw_audit_exit_code"] = result.returncode
        target.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(decision, indent=2))
        if decision["accepted_risks"]:
            print(
                "WARNING: DiskCache remains vulnerable. The proposed temporary risk exception is not a security fix."
            )
        return 1 if decision["blocked_findings"] else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Dependency security gate failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
