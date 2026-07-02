from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import JobSummary


class SummaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, summary: JobSummary) -> JobSummary:
        existing = (
            self.db.query(JobSummary)
            .filter(JobSummary.job_id == summary.job_id)
            .one_or_none()
        )
        if existing:
            existing.total_spend_inr = summary.total_spend_inr
            existing.total_spend_usd = summary.total_spend_usd
            existing.top_merchants = summary.top_merchants
            existing.anomaly_count = summary.anomaly_count
            existing.narrative = summary.narrative
            existing.risk_level = summary.risk_level
            self.db.commit()
            self.db.refresh(existing)
            return existing
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary

    def get_by_job(self, job_id: int) -> Optional[JobSummary]:
        return (
            self.db.query(JobSummary)
            .filter(JobSummary.job_id == job_id)
            .one_or_none()
        )
