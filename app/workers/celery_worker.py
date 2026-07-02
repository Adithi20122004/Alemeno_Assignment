from app.core.celery_app import celery_app

# Ensure task modules are imported so Celery registers them.
from app.tasks import process_job  # noqa: F401

__all__ = ["celery_app"]
