from __future__ import annotations

import io

import pandas as pd

from app.services.anomaly_service import AnomalyDetector
from app.services.csv_service import CsvCleaner
from app.services.summary_service import SummaryService

SAMPLE_CSV = """txn_id,date,merchant,amount,currency,status,category,account_id,notes
TXN1,04-09-2024,Flipkart,100.00,INR,SUCCESS,Shopping,ACC1,
TXN2,2024/02/05,Swiggy,$110.00,INR,success,Food,ACC1,
TXN3,17-02-2024,Zomato,50.00,USD,SUCCESS,Food,ACC1,
TXN4,07-05-2024,Amazon,50000.00,INR,failed,,ACC1,SUSPICIOUS
TXN5,14-08-2024,Swiggy,20.00,USD,SUCCESS,Food,ACC1,
TXN2,2024/02/05,Swiggy,$110.00,INR,success,Food,ACC1,
"""


def test_cleaner_normalises_and_dedupes(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(SAMPLE_CSV)
    cleaner = CsvCleaner()
    df = cleaner.clean(cleaner.read(str(p)))
    assert len(df) == 5  # duplicate TXN2 dropped
    # $ stripped
    assert float(df.loc[df.txn_id == "TXN2", "amount"].iloc[0]) == 110.00
    # status uppercased
    assert df["status"].str.isupper().all()
    # currency uppercased
    assert set(df["currency"].dropna().unique()).issubset({"INR", "USD"})


def test_anomaly_amount_and_usd_domestic(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(SAMPLE_CSV)
    cleaner = CsvCleaner()
    df = cleaner.clean(cleaner.read(str(p)))
    df = AnomalyDetector().detect(df)

    # TXN4 (50000 vs small median) must be anomaly
    row = df.loc[df.txn_id == "TXN4"].iloc[0]
    assert bool(row["is_anomaly"]) is True

    # TXN5 (Swiggy, USD) must be anomaly
    row = df.loc[df.txn_id == "TXN5"].iloc[0]
    assert bool(row["is_anomaly"]) is True


def test_summary_totals(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(SAMPLE_CSV)
    cleaner = CsvCleaner()
    df = cleaner.clean(cleaner.read(str(p)))
    df = AnomalyDetector().detect(df)
    stats = SummaryService().aggregate(df)
    assert stats["anomaly_count"] >= 2
    assert float(stats["total_spend_inr"]) > 0
    assert float(stats["total_spend_usd"]) > 0
    assert len(stats["top_merchants"]) <= 3
