from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.session import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    txn_id = Column(String(64), nullable=False, index=True)
    date = Column(Date, nullable=True)
    merchant = Column(String(255), nullable=True)
    amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(8), nullable=True)
    status = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)
    account_id = Column(String(64), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    is_anomaly = Column(Boolean, nullable=False, default=False)
    anomaly_reason = Column(String(255), nullable=True)

    llm_category = Column(String(64), nullable=True)
    llm_failed = Column(Boolean, nullable=False, default=False)

    job = relationship("Job", back_populates="transactions")

    __table_args__ = (
        Index("ix_txn_job_account", "job_id", "account_id"),
    )
