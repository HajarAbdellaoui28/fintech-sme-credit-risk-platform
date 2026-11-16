"""Regression test for RFC CSV quotes and Spark SQL NULL outcome filtering."""

import csv
from datetime import date, timedelta

import pytest

from fintech_risk.data import prepare_sba, spark_session


@pytest.mark.spark
def test_csv_quotes_and_null_charge_dates_preserve_paid_loans(tmp_path):
    path = tmp_path / "data/raw/sba/fixture.csv"
    path.parent.mkdir(parents=True)
    records = []
    for i in range(60):
        records.append(
            {
                "LoanNr_ChkDgt": str(i),
                "Name": f'Company {i} "quoted", LLC',
                "Zip": "10001",
                "NAICS": "541110",
                "MIS_Status": "CHGOFF" if i % 3 == 0 else "P I F",
                "GrAppv": "$100,000.00",
                "SBA_Appv": "$75,000.00",
                "NoEmp": "10",
                "State": "NY",
                "NewExist": "1",
                "LowDoc": "N",
                "RevLineCr": "N",
                "UrbanRural": "1",
                "ApprovalDate": (date(1999, 1, 1) + timedelta(days=i)).strftime("%d-%b-%y"),
                "ChgOffDate": "01-Jan-03" if i % 3 == 0 else "",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    spark = spark_session()
    try:
        frame = prepare_sba(spark, tmp_path)
    finally:
        spark.stop()
    assert len(frame) == 60
    assert int(frame.target.sum()) == 20
    for _, group in frame.groupby("split"):
        assert set(group.target) == {0, 1}
    assert (
        frame.loc[frame.split == "train", "approval_date"].max()
        < frame.loc[frame.split == "validation", "approval_date"].min()
    )
