"""Immutable-source audit and Spark preparation with frozen split manifests."""

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa
from scipy.io import arff
from sklearn.model_selection import train_test_split

from fintech_risk.config import ROOT, parameters, save_json
from fintech_risk.features import (
    CREDIT_CATEGORICAL,
    CREDIT_FEATURES,
    POLISH_FEATURES,
    polish_dictionary,
)


def spark_session():
    import pyspark
    from pyspark.sql import SparkSession

    # A global SPARK_HOME may point to another Spark version on Windows.
    # Override only this process, never the user's global installation.
    os.environ["SPARK_HOME"] = str(Path(pyspark.__file__).resolve().parent)
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    session = (
        SparkSession.builder.master("local[2]")
        .appName("fintech-data-engineering")
        .config("spark.driver.memory", "3g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .getOrCreate()
    )
    if session.version != pyspark.__version__:
        session.stop()
        raise RuntimeError("Python/JVM Spark version mismatch")
    return session


def source_fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_polish(path):
    records, _ = arff.loadarff(path)
    df = pd.DataFrame(records)
    df["target"] = df.pop("class").str.decode("ascii").astype(int)
    return df


def audit(root=ROOT):
    report = {
        "files": {},
        "polish": {},
        "limitations": [
            "SBA extraction date and open-loan coverage are not certified.",
            "Polish cohorts have no company IDs or calendar dates; exact overlap is not company overlap.",
            "Term may describe realized duration; excluded without original-contract evidence.",
        ],
    }
    hashes = {}
    for path in sorted((root / "data/raw").rglob("*")):
        if path.is_file():
            report["files"][str(path.relative_to(root))] = {
                "sha256": source_fingerprint(path),
                "bytes": path.stat().st_size,
            }
    for path in sorted((root / "data/raw/polish").glob("*.arff")):
        df = load_polish(path)
        report["polish"][path.name] = {
            "rows": len(df),
            "horizon_years": 6 - int(path.stem[0]),
            "labels": {str(k): int(v) for k, v in df.target.value_counts().items()},
            "missing": df.isna().sum().astype(int).to_dict(),
            "duplicate_profiles": int(df.duplicated(POLISH_FEATURES).sum()),
            "numeric_summary": df.describe(percentiles=[0.01, 0.5, 0.99]).to_dict(),
        }
        hashes[path.name] = set(pd.util.hash_pandas_object(df[POLISH_FEATURES], index=False))
    report["cross_cohort_exact_overlap"] = {
        f"{a}:{b}": len(hashes[a] & hashes[b]) for a in hashes for b in hashes if a < b
    }
    # pandas describes sparse columns with valid finite statistics for these datasets.
    save_json(root / "reports/generated/data_audit.json", report)
    save_json(root / "configs/polish_dictionary.json", polish_dictionary())
    return report


def validate_prepared(frame, features):
    schema = pa.DataFrameSchema(
        {
            **{
                name: pa.Column(
                    str if name in CREDIT_CATEGORICAL else float, nullable=True, coerce=True
                )
                for name in features
            },
            "target": pa.Column(int, pa.Check.isin([0, 1])),
            "split": pa.Column(str, pa.Check.isin(["train", "validation", "test"])),
            "row_id": pa.Column(str, unique=True),
        },
        strict=False,
    )
    schema.validate(frame, lazy=True)


def prepare_polish(spark, root=ROOT):
    from pyspark.sql import functions as F

    df = load_polish(root / "data/raw/polish/5year.arff")
    df["row_id"] = pd.util.hash_pandas_object(df[POLISH_FEATURES], index=False).astype(str)
    # Deduplicate the complete original vector BEFORE deriving simplified features.
    sdf = spark.createDataFrame(df).dropDuplicates(POLISH_FEATURES)
    for name in POLISH_FEATURES:
        sdf = sdf.withColumn(name, F.when(F.isnan(name), None).otherwise(F.col(name)))
    df = sdf.toPandas().sort_values("row_id").reset_index(drop=True)
    train, heldout = train_test_split(df.index, test_size=0.4, random_state=42, stratify=df.target)
    val, test = train_test_split(
        heldout, test_size=0.5, random_state=42, stratify=df.loc[heldout, "target"]
    )
    df["split"] = "train"
    df.loc[val, "split"] = "validation"
    df.loc[test, "split"] = "test"
    validate_prepared(df, POLISH_FEATURES)
    out = root / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "polish.parquet", index=False)
    complete = df[(df.split == "train") & df[POLISH_FEATURES].notna().all(axis=1)]
    # Descriptive examples, never chosen using held-out targets or predicted probabilities.
    ordered = complete.sort_values("Attr2")
    examples = []
    for label, fraction in [
        ("Passif relatif faible", 0.15),
        ("Passif relatif médian", 0.5),
        ("Passif relatif élevé", 0.85),
    ]:
        row = ordered.iloc[int((len(ordered) - 1) * fraction)]
        examples.append(
            {
                "label": label,
                "provenance": "UCI training cohort, demonstration only",
                "source_row_id": row.row_id,
                "features": {k: float(row[k]) for k in POLISH_FEATURES},
            }
        )
    save_json(root / "artifacts/demo_profiles.json", examples)
    save_json(out / "demo_profiles.json", examples)
    save_json(root / "reports/generated/polish_split.json", split_report(df))
    return df


def split_report(df):
    return {
        s: {
            "rows": int(len(g)),
            "positives": int(g.target.sum()),
            "ids_sha256": hashlib.sha256("\n".join(sorted(g.row_id)).encode()).hexdigest(),
        }
        for s, g in df.groupby("split")
    }


def prepare_sba(spark, root=ROOT):
    from pyspark.sql import functions as F

    paths = [p.resolve().as_uri() for p in sorted((root / "data/raw/sba").glob("*.csv"))]
    raw = (
        spark.read.option("header", True)
        .option("mode", "FAILFAST")
        .option("escape", '"')
        .option("multiLine", True)
        .csv(paths)
    )
    raw = raw.withColumn("status", F.regexp_replace(F.upper(F.trim("MIS_Status")), r"\s+", ""))
    counts = {str(r.status): r["count"] for r in raw.groupBy("status").count().collect()}
    if set(counts) - {"PIF", "CHGOFF", "None", ""}:
        raise ValueError(f"Unexpected target tokens after CSV parsing: {list(counts)}")
    sdf = raw.filter(F.col("status").isin("PIF", "CHGOFF"))
    has_charge_date = F.length(F.trim(F.coalesce(F.col("ChgOffDate"), F.lit("")))) > 0
    sdf = sdf.filter(~((F.col("status") == "PIF") & has_charge_date))
    for c in ["GrAppv", "SBA_Appv"]:
        sdf = sdf.withColumn(c, F.regexp_replace(F.col(c), r"[^0-9.\-]", "").cast("double"))
    sdf = sdf.withColumn("NoEmp", F.col("NoEmp").cast("double"))
    sdf = sdf.filter(
        (F.col("GrAppv") > 0)
        & (F.col("SBA_Appv") > 0)
        & (F.col("SBA_Appv") <= F.col("GrAppv"))
        & (F.col("NoEmp") >= 0)
    )
    sdf = sdf.withColumn("guarantee_ratio", F.col("SBA_Appv") / F.col("GrAppv"))
    sdf = sdf.withColumn(
        "NAICS2",
        F.when(F.col("NAICS").rlike("^[1-9][0-9]{5}$"), F.substring("NAICS", 1, 2)).otherwise(
            "UNKNOWN"
        ),
    )
    for c, allowed in {
        "NewExist": ["1", "2"],
        "UrbanRural": ["1", "2"],
        "LowDoc": ["Y", "N"],
        "RevLineCr": ["Y", "N"],
    }.items():
        sdf = sdf.withColumn(c, F.when(F.col(c).isin(allowed), F.col(c)).otherwise("UNKNOWN"))
    sdf = sdf.withColumn(
        "State", F.when(F.col("State").rlike("^[A-Z]{2}$"), F.col("State")).otherwise("UNKNOWN")
    )
    sdf = sdf.withColumn("approval_date", F.to_date("ApprovalDate", "dd-MMM-yy"))
    sdf = sdf.withColumn(
        "approval_date",
        F.when(F.year("approval_date") > 2020, F.add_months("approval_date", -1200)).otherwise(
            F.col("approval_date")
        ),
    )
    sdf = sdf.withColumn("target", (F.col("status") == "CHGOFF").cast("int"))
    sdf = sdf.withColumn(
        "borrower_group", F.sha2(F.concat_ws("|", F.upper(F.trim("Name")), "Zip"), 256)
    )
    sdf = sdf.select(
        *CREDIT_FEATURES,
        "target",
        "approval_date",
        "borrower_group",
        F.col("LoanNr_ChkDgt").alias("row_id"),
    ).dropDuplicates(["row_id"])
    sdf = sdf.filter(F.col("approval_date").isNotNull())
    df = sdf.toPandas().sort_values(["approval_date", "row_id"]).reset_index(drop=True)
    dates = pd.to_datetime(df.approval_date)
    a, b = dates.iloc[int(len(df) * 0.6)], dates.iloc[int(len(df) * 0.8)]
    df["split"] = np.where(dates < a, "train", np.where(dates < b, "validation", "test"))
    # Remove cross-split borrowers from earlier cohorts, preserving chronological order.
    ranks = df.split.map({"train": 0, "validation": 1, "test": 2})
    latest = ranks.groupby(df.borrower_group).transform("max")
    removed = int((ranks != latest).sum())
    df = df.loc[ranks == latest].copy()
    df.target = df.target.astype("int64")
    for split, group in df.groupby("split"):
        if set(group.target.unique()) != {0, 1}:
            raise ValueError(f"Both outcomes are required in SBA split {split}")
    validate_prepared(df, CREDIT_FEATURES)
    (root / "data/processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet(root / "data/processed/sba.parquet", index=False)
    save_json(
        root / "reports/generated/sba_split.json",
        {
            "raw_labels": counts,
            "boundaries": [str(a), str(b)],
            "cross_split_borrower_rows_removed": removed,
            "splits": split_report(df),
            "censoring": "Resolved historical outcomes only; observation cutoff unknown.",
            "term": "Excluded: contractual-original meaning not verified.",
        },
    )
    return df


def prepare(root=ROOT):
    from importlib.metadata import version

    audit(root)
    spark = spark_session()
    try:
        prepare_polish(spark, root)
        prepare_sba(spark, root)
    finally:
        spark.stop()
    save_json(
        root / "data/processed/preparation_manifest.json",
        {
            "seed": parameters()["seed"],
            "engine": "PySpark " + version("pyspark"),
            "polish_shared_split": True,
        },
    )
