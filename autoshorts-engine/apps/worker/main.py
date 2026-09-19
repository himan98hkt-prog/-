"""워커 프로세스 진입점.

    python -m apps.worker.main

API 와 별도 프로세스다. 브라우저를 닫아도, API 를 재시작해도 작업은 계속 돈다.
여러 개를 동시에 띄워도 된다 — 큐가 SKIP LOCKED 로 서로 다른 작업을 나눠 준다.
"""

from __future__ import annotations

from saas.worker import run_worker

if __name__ == "__main__":
    raise SystemExit(run_worker())
