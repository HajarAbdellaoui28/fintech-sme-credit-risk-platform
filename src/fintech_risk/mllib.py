"""Real distributed MLlib reference models; portable champions are trained separately."""

from fintech_risk.config import ROOT, save_json
from fintech_risk.data import spark_session
from fintech_risk.features import CREDIT_CATEGORICAL, CREDIT_NUMERIC
from fintech_risk.models import dataset, task_features


def benchmark():
    from pyspark.ml import Pipeline
    from pyspark.ml.classification import LogisticRegression, RandomForestClassifier
    from pyspark.ml.evaluation import BinaryClassificationEvaluator
    from pyspark.ml.feature import (
        Imputer,
        OneHotEncoder,
        StandardScaler,
        StringIndexer,
        VectorAssembler,
    )

    spark = spark_session()
    results = {}
    try:
        for task in ["sme", "bankruptcy_full", "credit"]:
            df = dataset(task)
            features = task_features(task)
            numerical = CREDIT_NUMERIC if task == "credit" else features
            sdf = spark.createDataFrame(
                df[features + ["target", "split"]].astype({"target": float})
            )
            train, test = sdf.filter("split = 'train'"), sdf.filter("split = 'test'")
            stages = [
                Imputer(
                    inputCols=numerical,
                    outputCols=[c + "_imputed" for c in numerical],
                    strategy="median",
                )
            ]
            assembled = [c + "_imputed" for c in numerical]
            if task == "credit":
                for c in CREDIT_CATEGORICAL:
                    stages.append(
                        StringIndexer(inputCol=c, outputCol=c + "_index", handleInvalid="keep")
                    )
                stages.append(
                    OneHotEncoder(
                        inputCols=[c + "_index" for c in CREDIT_CATEGORICAL],
                        outputCols=[c + "_encoded" for c in CREDIT_CATEGORICAL],
                        handleInvalid="keep",
                    )
                )
                assembled += [c + "_encoded" for c in CREDIT_CATEGORICAL]
            stages.extend(
                [
                    VectorAssembler(inputCols=assembled, outputCol="unscaled"),
                    StandardScaler(inputCol="unscaled", outputCol="features"),
                ]
            )
            prep = Pipeline(stages=stages).fit(train)
            tr, te = prep.transform(train).cache(), prep.transform(test).cache()
            results[task] = {}
            for name, estimator in [
                ("logistic", LogisticRegression(labelCol="target", maxIter=100, regParam=0.01)),
                (
                    "forest",
                    RandomForestClassifier(labelCol="target", numTrees=80, maxDepth=8, seed=42),
                ),
            ]:
                fitted = estimator.fit(tr)
                predictions = fitted.transform(te)
                results[task][name] = {
                    metric: BinaryClassificationEvaluator(
                        labelCol="target", metricName=metric
                    ).evaluate(predictions)
                    for metric in ["areaUnderROC", "areaUnderPR"]
                }
                results[task][name]["note"] = (
                    "MLlib areaUnderPR is not sklearn average_precision; no ranking across differing definitions."
                )
            tr.unpersist()
            te.unpersist()
            print(f"MLlib reference complete: {task}", flush=True)
        save_json(ROOT / "reports/generated/mllib_references.json", results)
    finally:
        spark.stop()
