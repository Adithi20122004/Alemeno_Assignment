from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bulk_insert(self, transactions: Iterable[Transaction]) -> None:
        self.db.add_all(list(transactions))
        self.db.commit()

    def list_by_job(self, job_id: int) -> List[Transaction]:
        return (
            self.db.query(Transaction)
            .filter(Transaction.job_id == job_id)
            .order_by(Transaction.id.asc())
            .all()
        )

    def list_anomalies(self, job_id: int) -> List[Transaction]:
        return (
            self.db.query(Transaction)
            .filter(Transaction.job_id == job_id, Transaction.is_anomaly.is_(True))
            .order_by(Transaction.id.asc())
            .all()
        )
