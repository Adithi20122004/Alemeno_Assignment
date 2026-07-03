from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Job ----------

class JobBase(BaseModel):
    filename: str
    status: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class JobRead(JobBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class JobCreateResponse(BaseModel):
    job_id: int
    status: str
    filename: str
    message: str = "Job accepted. Processing in background."


# ---------- Transaction ----------

class TransactionRead(BaseModel):
    id: int
    txn_id: str
    date: Optional[date] = None
    merchant: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[str] = None
    notes: Optional[str] = None
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_failed: bool

    model_config = ConfigDict(from_attributes=True)


# ---------- Summary ----------

class SummaryRead(BaseModel):
    total_spend_inr: Optional[Decimal] = None
    total_spend_usd: Optional[Decimal] = None
    top_merchants: Optional[list] = None
    anomaly_count: int = 0
    narrative: Optional[str] = None
    risk_level: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Composite ----------

class JobStatusResponse(BaseModel):
    id: int
    filename: str
    status: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    summary: Optional[SummaryRead] = None


class JobResultsResponse(BaseModel):
    job: JobRead
    summary: Optional[SummaryRead] = None
    transactions: List[TransactionRead] = Field(default_factory=list)
    anomalies: List[TransactionRead] = Field(default_factory=list)
