from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Job, JobStatus


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, filename: str) -> Job:
        job = Job(filename=filename, status=JobStatus.PENDING)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> Optional[Job]:
        return self.db.get(Job, job_id)

    def list(self, status: Optional[str] = None) -> List[Job]:
        q = self.db.query(Job)
        if status:
            try:
                q = q.filter(Job.status == JobStatus(status.upper()))
            except ValueError:
                return []
        return q.order_by(Job.created_at.desc()).all()

    def mark_processing(self, job: Job) -> Job:
        job.status = JobStatus.PROCESSING
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_completed(
        self,
        job: Job,
        *,
        row_count_raw: int,
        row_count_clean: int,
    ) -> Job:
        job.status = JobStatus.COMPLETED
        job.row_count_raw = row_count_raw
        job.row_count_clean = row_count_clean
        job.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job: Job, error: str) -> Job:
        job.status = JobStatus.FAILED
        job.error_message = error[:2000]
        job.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job
