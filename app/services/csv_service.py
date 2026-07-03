from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes",
]

_CURRENCY_ALIASES = {
    "INR": "INR",
    "RS": "INR",
    "RUPEE": "INR",
    "USD": "USD",
    "$": "USD",
    "US$": "USD",
}


def _parse_date(value: Any) -> Optional[date]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) and not isinstance(value, datetime) else value.date()
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:  # pragma: no cover
        return None


def _clean_amount(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"[^\d\.\-]", "", s)
    if s in {"", "-", "."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _clean_currency(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    return _CURRENCY_ALIASES.get(s, s)


def _clean_status(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    return s or None


def _clean_str(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s or None


class CsvCleaner:
    """Reads and normalizes a transactions CSV."""

    def read(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path, dtype=str, keep_default_na=True)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
        return df

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        raw = df.copy()
        raw["date"] = raw["date"].apply(_parse_date)
        raw["amount"] = raw["amount"].apply(_clean_amount)
        raw["currency"] = raw["currency"].apply(_clean_currency)
        raw["status"] = raw["status"].apply(_clean_status)
        raw["merchant"] = raw["merchant"].apply(_clean_str)
        raw["category"] = raw["category"].apply(_clean_str)
        raw["account_id"] = raw["account_id"].apply(_clean_str)
        raw["notes"] = raw["notes"].apply(_clean_str)
        raw["txn_id"] = raw["txn_id"].apply(_clean_str)

        # Drop rows with no txn_id or amount (unrecoverable)
        raw = raw.dropna(subset=["txn_id"])

        # Remove exact duplicates by txn_id (keep first)
        raw = raw.drop_duplicates(subset=["txn_id"], keep="first")

        # Fill missing category with "Unknown" placeholder (LLM step fills real value)
        raw["category"] = raw["category"].where(raw["category"].notna(), None)

        return raw.reset_index(drop=True)

    def to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        records = df.to_dict(orient="records")
        # Normalize NaN → None
        cleaned: List[Dict[str, Any]] = []
        for r in records:
            cleaned.append({k: (None if pd.isna(v) else v) for k, v in r.items()})
        return cleaned
