from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List

import pandas as pd
from celery import shared_task

from app.core.celery_app import celery_app  # noqa: F401  (register with app)
from app.database.session import SessionLocal
from app.llm.gemini_client import get_gemini_client
from app.models import JobSummary, Transaction
from app.repositories import (
    JobRepository,
    SummaryRepository,
    TransactionRepository,
)
from app.services import AnomalyDetector, CsvCleaner, SummaryService

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def _risk_from(anomaly_count: int, total_usd: float) -> str:
    if anomaly_count == 0:
        return "LOW"
    if anomaly_count > 3 or total_usd > 20000:
        return "HIGH"
    return "MEDIUM"


@shared_task(name="process_job", bind=True, max_retries=0)
def process_job_task(self, job_id: int, file_path: str) -> Dict[str, Any]:
    logger.info("Job %s: pipeline starting for %s", job_id, file_path)

    db = SessionLocal()
    job_repo = JobRepository(db)
    txn_repo = TransactionRepository(db)
    summary_repo = SummaryRepository(db)

    job = job_repo.get(job_id)
    if job is None:
        db.close()
        raise RuntimeError(f"Job {job_id} not found")

    try:
        job_repo.mark_processing(job)

        # ---- Step 1 & 2: Read + Clean ----
        cleaner = CsvCleaner()
        raw_df = cleaner.read(file_path)
        row_count_raw = len(raw_df)
        clean_df = cleaner.clean(raw_df)

        # ---- Step 4: Anomaly detection ----
        detector = AnomalyDetector()
        clean_df = detector.detect(clean_df)

        # ---- Step 5: LLM categorization for missing categories ----
        gemini = get_gemini_client()
        missing_mask = clean_df["category"].isna() | (clean_df["category"] == "")
        missing_df = clean_df[missing_mask]

        llm_map: Dict[str, str] = {}
        llm_failed_ids: set = set()

        if not missing_df.empty:
            payload = [
                {
                    "txn_id": str(row["txn_id"]),
                    "merchant": row.get("merchant") or "",
                    "amount": float(row["amount"]) if pd.notna(row.get("amount")) else 0,
                    "currency": row.get("currency") or "",
                    "notes": row.get("notes") or "",
                }
                for _, row in missing_df.iterrows()
            ]
            for start in range(0, len(payload), BATCH_SIZE):
                batch = payload[start : start + BATCH_SIZE]
                result = gemini.categorize_batch(batch)
                if result is None:
                    llm_failed_ids.update(item["txn_id"] for item in batch)
                    logger.warning(
                        "Job %s: Gemini categorization failed for batch of %d",
                        job_id,
                        len(batch),
                    )
                else:
                    llm_map.update(result)

        # ---- Step 3: Persist cleaned transactions ----
        txns: List[Transaction] = []
        for _, row in clean_df.iterrows():
            tid = str(row["txn_id"])
            llm_cat = llm_map.get(tid)
            final_category = row.get("category") or llm_cat or None

            amount_val = row.get("amount")
            if amount_val is not None and pd.isna(amount_val):
                amount_val = None

            txns.append(
                Transaction(
                    job_id=job_id,
                    txn_id=tid,
                    date=row.get("date") if pd.notna(row.get("date")) else None,
                    merchant=row.get("merchant"),
                    amount=Decimal(str(amount_val)) if amount_val is not None else None,
                    currency=row.get("currency"),
                    status=row.get("status"),
                    category=final_category,
                    account_id=row.get("account_id"),
                    notes=row.get("notes"),
                    is_anomaly=bool(row.get("is_anomaly", False)),
                    anomaly_reason=row.get("anomaly_reason"),
                    llm_category=llm_cat,
                    llm_failed=tid in llm_failed_ids,
                )
            )
        txn_repo.bulk_insert(txns)

        # ---- Step 6: Summary ----
        summarizer = SummaryService()
        stats = summarizer.aggregate(clean_df)

        # Ask Gemini to generate narrative + risk (fallback to rules if it fails)
        llm_summary = gemini.summarize(
            {
                "total_spend_inr": float(stats["total_spend_inr"]),
                "total_spend_usd": float(stats["total_spend_usd"]),
                "top_merchants": stats["top_merchants"],
                "anomaly_count": stats["anomaly_count"],
            }
        )

        if llm_summary is None:
            narrative = (
                f"Processed {len(clean_df)} transactions with "
                f"{stats['anomaly_count']} anomalies flagged. "
                f"Total INR spend {stats['total_spend_inr']} and USD spend {stats['total_spend_usd']}."
            )
            risk_level = _risk_from(stats["anomaly_count"], float(stats["total_spend_usd"]))
        else:
            narrative = llm_summary.get("narrative") or ""
            risk_level = (llm_summary.get("risk_level") or "").upper() or _risk_from(
                stats["anomaly_count"], float(stats["total_spend_usd"])
            )
            if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
                risk_level = _risk_from(stats["anomaly_count"], float(stats["total_spend_usd"]))

        summary_repo.upsert(
            JobSummary(
                job_id=job_id,
                total_spend_inr=stats["total_spend_inr"],
                total_spend_usd=stats["total_spend_usd"],
                top_merchants=stats["top_merchants"],
                anomaly_count=stats["anomaly_count"],
                narrative=narrative,
                risk_level=risk_level,
            )
        )

        # ---- Step 7: Complete ----
        job_repo.mark_completed(
            job,
            row_count_raw=row_count_raw,
            row_count_clean=len(clean_df),
        )
        logger.info(
            "Job %s: completed. raw=%d clean=%d anomalies=%d",
            job_id,
            row_count_raw,
            len(clean_df),
            stats["anomaly_count"],
        )
        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "row_count_raw": row_count_raw,
            "row_count_clean": len(clean_df),
            "anomalies": stats["anomaly_count"],
        }

    except Exception as exc:
        logger.exception("Job %s: failed", job_id)
        job_repo.mark_failed(job, str(exc))
        return {"job_id": job_id, "status": "FAILED", "error": str(exc)}
    finally:
        db.close()
