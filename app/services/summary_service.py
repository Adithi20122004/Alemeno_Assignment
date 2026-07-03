from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class SummaryService:
    """Aggregates cleaned transactions into totals + top merchants."""

    def aggregate(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty:
            return {
                "total_spend_inr": Decimal("0"),
                "total_spend_usd": Decimal("0"),
                "top_merchants": [],
                "anomaly_count": 0,
            }

        amounts = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        currencies = df["currency"].fillna("").str.upper()

        total_inr = float(amounts[currencies == "INR"].sum())
        total_usd = float(amounts[currencies == "USD"].sum())

        merchant_totals = (
            df.assign(_amt=amounts)
            .groupby(df["merchant"].fillna("UNKNOWN"))["_amt"]
            .sum()
            .sort_values(ascending=False)
        )
        top_merchants: List[Dict[str, Any]] = [
            {"merchant": str(m), "total_amount": round(float(v), 2)}
            for m, v in merchant_totals.head(3).items()
        ]

        anomaly_count = int(df.get("is_anomaly", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())

        return {
            "total_spend_inr": Decimal(str(round(total_inr, 2))),
            "total_spend_usd": Decimal(str(round(total_usd, 2))),
            "top_merchants": top_merchants,
            "anomaly_count": anomaly_count,
        }
