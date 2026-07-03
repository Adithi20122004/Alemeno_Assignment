from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.session import Base


class JobSummary(Base):
    __tablename__ = "job_summaries"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    total_spend_inr = Column(Numeric(18, 2), nullable=True)
    total_spend_usd = Column(Numeric(18, 2), nullable=True)
    top_merchants = Column(JSONB, nullable=True)
    anomaly_count = Column(Integer, nullable=False, default=0)
    narrative = Column(Text, nullable=True)
    risk_level = Column(String(16), nullable=True)  # LOW | MEDIUM | HIGH

    job = relationship("Job", back_populates="summary")
