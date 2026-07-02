from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.repositories import (
    JobRepository,
    SummaryRepository,
    TransactionRepository,
)
from app.schemas import (
    JobCreateResponse,
    JobRead,
    JobResultsResponse,
    JobStatusResponse,
    SummaryRead,
    TransactionRead,
)
from app.tasks.process_job import process_job_task
from app.utils.file_utils import save_upload

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/upload",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_job(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    dest_path, size = save_upload(file)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size} bytes). Max {settings.MAX_UPLOAD_MB} MB.",
        )
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    job = JobRepository(db).create(filename=file.filename)
    process_job_task.delay(job.id, dest_path)
    logger.info("Job %s queued for %s (%d bytes)", job.id, file.filename, size)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status.value,
        filename=job.filename,
    )


@router.get("", response_model=List[JobRead])
def list_jobs(
    status: Optional[str] = Query(default=None, description="PENDING|PROCESSING|COMPLETED|FAILED"),
    db: Session = Depends(get_db),
) -> List[JobRead]:
    jobs = JobRepository(db).list(status=status)
    return [
        JobRead(
            id=j.id,
            filename=j.filename,
            status=j.status.value,
            row_count_raw=j.row_count_raw,
            row_count_clean=j.row_count_clean,
            created_at=j.created_at,
            completed_at=j.completed_at,
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    summary = None
    if job.status.value == "COMPLETED":
        s = SummaryRepository(db).get_by_job(job_id)
        if s:
            summary = SummaryRead.model_validate(s)

    return JobStatusResponse(
        id=job.id,
        filename=job.filename,
        status=job.status.value,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        summary=summary,
    )


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def job_results(job_id: int, db: Session = Depends(get_db)) -> JobResultsResponse:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status.value != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed yet (status={job.status.value})",
        )

    txn_repo = TransactionRepository(db)
    all_txns = txn_repo.list_by_job(job_id)
    anomalies = [t for t in all_txns if t.is_anomaly]
    summary = SummaryRepository(db).get_by_job(job_id)

    return JobResultsResponse(
        job=JobRead(
            id=job.id,
            filename=job.filename,
            status=job.status.value,
            row_count_raw=job.row_count_raw,
            row_count_clean=job.row_count_clean,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        ),
        summary=SummaryRead.model_validate(summary) if summary else None,
        transactions=[TransactionRead.model_validate(t) for t in all_txns],
        anomalies=[TransactionRead.model_validate(t) for t in anomalies],
    )
