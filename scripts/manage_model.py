import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from fintech_risk.config import ROOT
from fintech_risk.registry import promote, rollback

load_dotenv(ROOT / ".env")
p = argparse.ArgumentParser()
p.add_argument("--action", choices=["promote", "rollback"], required=True)
p.add_argument("--task", choices=["sme", "bankruptcy_full", "credit"], required=True)
p.add_argument("--candidate", default="")
p.add_argument("--reason", default="Approved operator model delivery")
args = p.parse_args()
token = os.environ.get("ADMIN_TOKEN", "")
if args.action == "promote":
    result = promote(args.task, Path(args.candidate), token, args.reason)
else:
    result = rollback(args.task, token, args.reason)
print({"task": args.task, "version": result["version"], "action": args.action})
