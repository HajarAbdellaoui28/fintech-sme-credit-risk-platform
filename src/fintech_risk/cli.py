"""Resource-aware command line for reproducible offline workflows."""

import argparse

from dotenv import load_dotenv

from fintech_risk.config import ROOT


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="FinTech three-model platform")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit")
    sub.add_parser("prepare")
    for name in ["train", "retrain"]:
        p = sub.add_parser(name)
        p.add_argument("--task", choices=["all", "sme", "bankruptcy_full", "credit"], default="all")
        p.add_argument("--trials", type=int, default=None)
        p.add_argument("--limit", type=int, default=None)
        p.add_argument("--no-register", action="store_true")
        p.add_argument("--additional-training", default=None)
    p = sub.add_parser("admit")
    p.add_argument("--task", choices=["sme", "bankruptcy_full", "credit"], required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--evidence", required=True)
    sub.add_parser("mllib")
    sub.add_parser("compare")
    p = sub.add_parser("pipeline-train")
    p.add_argument("--task", choices=["all", "sme", "bankruptcy_full", "credit"], default="all")
    p.add_argument("--trials", type=int, default=None)
    sub.add_parser("compare-snapshots")
    p = sub.add_parser("drift")
    p.add_argument("--task", required=True, choices=["sme", "bankruptcy_full", "credit"])
    p.add_argument("--current", required=True)
    args = parser.parse_args()
    if args.command == "audit":
        from fintech_risk.data import audit

        audit()
    elif args.command == "prepare":
        from fintech_risk.data import prepare

        prepare()
    elif args.command == "admit":
        from pathlib import Path

        from fintech_risk.retraining import admit

        print(admit(args.task, Path(args.data), Path(args.evidence)))
    elif args.command in {"train", "retrain"}:
        from fintech_risk.models import train_task

        for task in ["sme", "bankruptcy_full", "credit"] if args.task == "all" else [args.task]:
            path, _ = train_task(
                task,
                args.trials,
                args.limit,
                register=not args.no_register,
                candidate=args.command == "retrain",
                additional_training=args.additional_training,
            )
            print(path, flush=True)
    elif args.command == "pipeline-train":
        from fintech_risk.pipeline import pipeline_train

        pipeline_train(None if args.task == "all" else [args.task], args.trials)
    elif args.command == "compare-snapshots":
        from fintech_risk.pipeline import compare_snapshots

        compare_snapshots()
    elif args.command == "mllib":
        from fintech_risk.mllib import benchmark

        benchmark()
    elif args.command == "compare":
        from fintech_risk.models import compare_polish

        compare_polish()
    elif args.command == "drift":
        from fintech_risk.monitoring import drift_report

        print(drift_report(args.task, ROOT / args.current))


if __name__ == "__main__":
    main()
