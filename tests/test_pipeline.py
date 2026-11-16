"""Regression invariant: DVC may replace snapshots, never the live model store."""

from pathlib import Path

import yaml

from fintech_risk.config import ROOT


def test_dvc_outputs_never_overlap_live_artifacts():
    pipeline = yaml.safe_load((ROOT / "dvc.yaml").read_text(encoding="utf-8"))
    protected = (ROOT / "artifacts").resolve()
    for stage in pipeline["stages"].values():
        for output in stage.get("outs", []):
            relative = output if isinstance(output, str) else next(iter(output))
            target = (ROOT / Path(relative)).resolve()
            assert not target.is_relative_to(protected), (
                f"DVC output overlaps live store: {relative}"
            )
            assert not protected.is_relative_to(target), (
                f"DVC output contains live store: {relative}"
            )
