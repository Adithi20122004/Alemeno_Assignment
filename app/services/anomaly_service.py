from __future__ import annotations

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

FOREIGN_MERCHANT_BLOCKLIST = {"SWIGGY", "OLA", "IRCTC"}
AMOUNT_MULTIPLIER = 3.0


class AnomalyDetector:
    """Rule-based anomaly detection on cleaned transactions."""

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            df["is_anomaly"] = False
            df["anomaly_reason"] = None
            return df

        df = df.copy()
        df["is_anomaly"] = False
        df["anomaly_reason"] = None

        # Rule 1: amount > 3x median(account_id)
        medians = df.groupby("account_id")["amount"].median(numeric_only=True)
        for idx, row in df.iterrows():
            amt = row.get("amount")
            acct = row.get("account_id")
            if amt is None or pd.isna(amt) or acct is None:
                continue
            med = medians.get(acct)
            if med is None or pd.isna(med) or med <= 0:
                continue
            if amt > AMOUNT_MULTIPLIER * med:
                df.at[idx, "is_anomaly"] = True
                df.at[idx, "anomaly_reason"] = (
                    f"amount {amt:.2f} > {AMOUNT_MULTIPLIER}x account median ({med:.2f})"
                )

        # Rule 2: currency USD with merchant in blocklist (domestic-only merchants)
        for idx, row in df.iterrows():
            cur = (row.get("currency") or "").upper()
            merch = (row.get("merchant") or "").upper()
            if cur == "USD" and merch in FOREIGN_MERCHANT_BLOCKLIST:
                df.at[idx, "is_anomaly"] = True
                existing = df.at[idx, "anomaly_reason"]
                reason = f"USD currency with domestic merchant {merch}"
                df.at[idx, "anomaly_reason"] = (
                    f"{existing}; {reason}" if existing else reason
                )

        return df

    @staticmethod
    def count(df: pd.DataFrame) -> int:
        if "is_anomaly" not in df.columns:
            return 0
        return int(df["is_anomaly"].fillna(False).astype(bool).sum())
