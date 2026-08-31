SHELL := /bin/bash
COMPOSE ?= docker compose
PY ?= python3
VENV ?= .venv
VPY := $(VENV)/bin/python

.PHONY: help up down logs check-tools venv test test-server test-web e2e seed \
        golden lint demo-m0 demo-m3 demo-judge

help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | column -t -s $$'\t'

up:            ## 6개 서비스 기동
	$(COMPOSE) up -d --build
	@echo "web  http://localhost:$${WEB_PORT:-3000}"
	@echo "api  http://localhost:$${API_PORT:-8000}/docs"

down:          ## 종료
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

venv: $(VENV)/.stamp
$(VENV)/.stamp: server/requirements-dev.txt
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -q --upgrade pip
	$(VPY) -m pip install -q -r server/requirements-dev.txt
	@touch $@

check-tools: venv  ## mscore/audiveris/ffmpeg/music21/torch+체크포인트/chromium 6종 검증
	$(VPY) scripts/check_tools.py

test: test-server test-web  ## 전체 테스트

test-server: venv
	$(VPY) -m pytest server/tests -q

test-web:
	cd web && pnpm vitest run

e2e:
	cd web && pnpm playwright test

golden: venv    ## 골든 20건 회귀 (검증통과율·musicality·비평총점)
	$(VPY) -m pytest server/tests/golden -q --golden-report=docs/golden-report.md

seed: venv
	$(VPY) scripts/seed_corpus.py

lint: venv
	$(VPY) -m ruff check server scripts
	$(VPY) -m mypy server/app

demo-m0: check-tools  ## M0 완료 기준 재현
	@echo "M0 OK"

demo-m3: venv   ## 모티브→Plan→Realize→비평 데모 (오프라인 스텁 엔진)
	$(VPY) scripts/demo_compose.py

demo-judge: venv ## 모의 심사 3인 패널 데모
	$(VPY) scripts/demo_judge.py
