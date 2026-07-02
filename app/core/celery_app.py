from __future__ import annotations

from celery import Celery

from app.core.config import settings


def make_celery() -> Celery:
    app = Celery(
        "txn_cleaner",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.tasks.process_job"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_time_limit=15 * 60,
        task_soft_time_limit=12 * 60,
        worker_max_tasks_per_child=50,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = make_celery()
