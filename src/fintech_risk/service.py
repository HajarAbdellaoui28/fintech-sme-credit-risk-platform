"""Version-pinned inference with startup artifact integrity validation."""

from functools import lru_cache

import joblib
import pandas as pd

from fintech_risk.config import ROOT, parameters, read_json
from fintech_risk.data import source_fingerprint
from fintech_risk.finance import analyse_sme, grade
from fintech_risk.models import explain
from fintech_risk.schemas import CreditInput, FullPolishInput, SMEInput

CONTRACTS = {"sme": SMEInput, "bankruptcy_full": FullPolishInput, "credit": CreditInput}
WARNINGS_FR = {
    "Historical Polish population; external validity not established.": "Population polonaise historique ; validité dans d'autres populations non établie.",
    "Bankruptcy probability is not credit PD.": "La probabilité de faillite n'est pas une PD de crédit validée.",
    "Historically approved and resolved loans only; censoring and selection bias.": "Prêts historiquement approuvés et résolus uniquement ; biais de sélection et de censure.",
    "Not a one-year PD or validated pre-approval decision.": "Horizon variable ; aucune PD annuelle ni décision avant accord validée.",
    "Validation Brier is worse than the prevalence-only baseline; probability accuracy is limited.": "Le Brier en validation est moins bon que la référence de prévalence ; la précision des probabilités est limitée.",
}


class ModelUnavailable(RuntimeError):
    pass


class ModelService:
    def __init__(self, manifest_path=None):
        self._cached_explanation = lru_cache(maxsize=256)(self._uncached_explanation)
        self.bundles = {}
        self.errors = {}
        self.grade_boundaries = parameters()["decision"]["grade_boundaries"]
        path = manifest_path or ROOT / "artifacts/deployment.json"
        if not path.exists():
            self.errors["manifest"] = "No approved deployment manifest"
            return
        manifest = read_json(path)
        for task, ref in manifest.items():
            try:
                directory = (ROOT / ref["path"]).resolve()
                if not directory.is_relative_to((ROOT / "artifacts").resolve()):
                    raise ValueError("Artifact path outside trusted store")
                if source_fingerprint(directory / "model.joblib") != ref["model_sha256"]:
                    raise ValueError("Artifact digest mismatch")
                metadata = read_json(directory / "metadata.json")
                model = joblib.load(directory / "model.joblib")
                if model.task != task or model.features != metadata["features"]:
                    raise ValueError("Model task or feature contract mismatch")
                estimator = model.pipeline.named_steps["estimator"]
                if "n_jobs" in estimator.get_params(deep=False):
                    # A single-row request should not create nested worker pools.
                    # This changes scheduling only; fitted weights remain untouched.
                    estimator.set_params(n_jobs=1)
                background = pd.read_parquet(directory / "background.parquet")
                bounds = background.quantile([0.01, 0.99], numeric_only=True)
                self.bundles[task] = {
                    "model": model,
                    "metadata": metadata,
                    "background": background,
                    "directory": directory,
                    "version": ref["version"],
                    "reference_bounds": {
                        key: (bounds.loc[0.01, key], bounds.loc[0.99, key])
                        for key in bounds.columns
                    },
                }
            except (OSError, ValueError, ImportError) as exc:
                self.errors[task] = str(exc)

    def info(self):
        from fintech_risk.config import MODEL_NAMES

        return {
            task: (
                {
                    "available": True,
                    "version": b["version"],
                    **{
                        k: b["metadata"][k]
                        for k in [
                            "model_name",
                            "horizon",
                            "predicted_event",
                            "schema_version",
                            "features",
                            "winner",
                            "calibrated",
                            "validation",
                            "test",
                            "warnings",
                        ]
                    },
                }
                if (b := self.bundles.get(task))
                else {
                    "available": False,
                    "model_name": name,
                    "reason": self.errors.get(task, "Approved model not loaded"),
                }
            )
            for task, name in MODEL_NAMES.items()
        }

    def get(self, task):
        if task not in self.bundles:
            raise ModelUnavailable(f"Model {task} is unavailable")
        return self.bundles[task]

    @staticmethod
    def frame(task, validated):
        if task == "sme":
            values = {"Attr2": validated.debt_ratio, "Attr4": validated.current_ratio}
        elif task == "bankruptcy_full":
            values = validated.features
        else:
            values = validated.features()
        return pd.DataFrame([values])

    def predict(self, task, validated, include_explanation=False):
        bundle = self.get(task)
        metadata = bundle["metadata"]
        frame = self.frame(task, validated)
        probability = float(bundle["model"].predict_proba(frame)[0, 1])
        result = {
            "available": True,
            "predicted_event": metadata["predicted_event"],
            "horizon": metadata["horizon"],
            "probability": probability,
            "model_name": metadata["model_name"],
            "model_version": bundle["version"],
            "input_schema_version": metadata["schema_version"],
            "indicative_grade": grade(probability, self.grade_boundaries),
            "grade_label": "Classification indicative, non bancaire",
            "risk_flag": probability >= metadata["threshold"],
            "threshold": metadata["threshold"],
            "warnings": [WARNINGS_FR.get(w, w) for w in metadata["warnings"]],
        }
        values = frame.iloc[0]
        extremes = [
            key
            for key, (low, high) in bundle["reference_bounds"].items()
            if key in values and not low <= values[key] <= high
        ]
        if extremes:
            result["warnings"].append(
                "En dehors de la plage de référence échantillonnée : " + ", ".join(extremes)
            )
        if task == "sme":
            result = {"prediction": result, "financial_analysis": analyse_sme(validated)}
        if include_explanation:
            result["explanation"] = self.explanation(task, validated)
        return result

    def explanation(self, task, validated):
        bundle = self.get(task)
        frame = self.frame(task, validated)
        key = tuple(str(frame.iloc[0][k]) for k in bundle["model"].features)
        return self._cached_explanation(task, key)

    def _uncached_explanation(self, task, key):
        bundle = self.get(task)
        numeric = set(bundle["model"].features) - {
            "NAICS2",
            "NewExist",
            "State",
            "UrbanRural",
            "LowDoc",
            "RevLineCr",
        }
        frame = pd.DataFrame(
            [
                {
                    name: float(value) if name in numeric else value
                    for name, value in zip(bundle["model"].features, key, strict=True)
                }
            ]
        )
        return {
            "model_name": bundle["metadata"]["model_name"],
            "model_version": bundle["version"],
            **explain(bundle["model"], frame, bundle["background"]),
        }
