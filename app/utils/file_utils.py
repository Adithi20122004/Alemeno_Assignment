from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


def ensure_upload_dir() -> Path:
    p = Path(settings.UPLOAD_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(file: UploadFile) -> tuple[str, int]:
    ensure_upload_dir()
    ext = os.path.splitext(file.filename or "upload.csv")[1] or ".csv"
    unique = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / unique
    size = 0
    with open(dest, "wb") as f:
        while True:
            chunk = file.file.read(1024 * 64)
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
    return str(dest), size
