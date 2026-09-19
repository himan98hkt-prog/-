"""API 프로세스 진입점.

    uvicorn apps.api.main:app --port 8000

환경변수
--------
``AUTOSHORTS_DATABASE_URL``  PostgreSQL DSN
``AUTOSHORTS_UPLOAD_SECRET`` presigned 업로드 서명 키(운영에서는 필수)
``AUTOSHORTS_STORAGE_ROOT``  로컬 오브젝트 스토리지 루트
"""

from __future__ import annotations

import os

from saas.api import AppContext, create_app
from saas.db import Database


def build_app():
    db = Database(os.environ.get("AUTOSHORTS_DATABASE_URL") or None)
    context = AppContext(
        db,
        storage_root=os.environ.get("AUTOSHORTS_STORAGE_ROOT", "var/storage"),
        upload_secret=os.environ.get("AUTOSHORTS_UPLOAD_SECRET", ""),
    )
    return create_app(context)


app = build_app()
