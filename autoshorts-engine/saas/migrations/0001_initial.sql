-- Phase 2 초기 스키마.
--
-- 규칙 세 가지:
--   1. 사용자 데이터가 들어가는 모든 표는 workspace_id 를 직접 갖는다.
--      조인을 타고 올라가야 소유자를 알 수 있는 구조는 격리 누수를 만든다.
--   2. 상태 문자열은 CHECK 로 고정한다. 애플리케이션 버그가 DB 를 오염시키지 못한다.
--   3. 금액은 정수(마이크로달러/크레딧)로만 저장한다. 부동소수 누적 오차 금지.

CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    email           TEXT        NOT NULL UNIQUE,
    display_name    TEXT        NOT NULL DEFAULT '',
    password_hash   TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    disabled_at     TIMESTAMPTZ
);

CREATE TABLE sessions (
    token_hash  TEXT PRIMARY KEY,                  -- 원문 토큰은 저장하지 않는다
    user_id     TEXT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    user_agent  TEXT        NOT NULL DEFAULT ''
);
CREATE INDEX sessions_user_idx ON sessions (user_id);

CREATE TABLE workspaces (
    id              TEXT PRIMARY KEY,
    name            TEXT        NOT NULL,
    owner_user_id   TEXT        NOT NULL REFERENCES users(id),
    credit_balance  BIGINT      NOT NULL DEFAULT 0,   -- 사용 가능 크레딧
    credit_reserved BIGINT      NOT NULL DEFAULT 0,   -- 실행 중 작업이 잡아둔 크레딧
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT workspaces_credits_nonneg
        CHECK (credit_balance >= 0 AND credit_reserved >= 0)
);

CREATE TABLE workspace_members (
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id      TEXT        NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    role         TEXT        NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);
CREATE INDEX workspace_members_user_idx ON workspace_members (user_id);

CREATE TABLE projects (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name         TEXT        NOT NULL,
    content_mode TEXT        NOT NULL DEFAULT 'auto',
    revision     INTEGER     NOT NULL DEFAULT 1,      -- 변경마다 증가
    created_by   TEXT        NOT NULL REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at  TIMESTAMPTZ
);
CREATE INDEX projects_workspace_idx ON projects (workspace_id, created_at DESC);

-- 프로젝트 이력. Phase 6 의 "되돌리기"가 여기에 얹힌다.
CREATE TABLE project_revisions (
    project_id  TEXT        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision    INTEGER     NOT NULL,
    change_kind TEXT        NOT NULL,
    changed_by  TEXT        REFERENCES users(id),
    snapshot    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, revision)
);

CREATE TABLE source_assets (
    id                TEXT PRIMARY KEY,
    workspace_id      TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id        TEXT        NOT NULL REFERENCES projects(id)   ON DELETE CASCADE,
    -- provenance: 이 미디어가 어디서 왔는지 항상 말할 수 있어야 한다
    origin            TEXT        NOT NULL CHECK (origin IN ('upload', 'url', 'generated')),
    source_url        TEXT        NOT NULL DEFAULT '',
    original_filename TEXT        NOT NULL DEFAULT '',
    uploaded_by       TEXT        REFERENCES users(id),
    storage_key       TEXT        NOT NULL DEFAULT '',
    content_type      TEXT        NOT NULL DEFAULT '',
    size_bytes        BIGINT      NOT NULL DEFAULT 0,
    checksum_sha256   TEXT        NOT NULL DEFAULT '',
    duration_seconds  DOUBLE PRECISION,
    rights_status     TEXT        NOT NULL DEFAULT 'unverified'
                      CHECK (rights_status IN ('owned', 'licensed', 'creative_commons', 'unverified')),
    upload_state      TEXT        NOT NULL DEFAULT 'pending'
                      CHECK (upload_state IN ('pending', 'uploaded', 'failed')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX source_assets_project_idx ON source_assets (workspace_id, project_id, created_at DESC);

CREATE TABLE rights_confirmations (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id)   ON DELETE CASCADE,
    asset_id     TEXT        NOT NULL REFERENCES source_assets(id) ON DELETE CASCADE,
    status       TEXT        NOT NULL
                 CHECK (status IN ('owned', 'licensed', 'creative_commons', 'unverified')),
    confirmed_by TEXT        REFERENCES users(id),
    evidence_uri TEXT        NOT NULL DEFAULT '',
    note         TEXT        NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX rights_confirmations_asset_idx ON rights_confirmations (asset_id, created_at DESC);

CREATE TABLE upload_tickets (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id)    ON DELETE CASCADE,
    project_id   TEXT        NOT NULL REFERENCES projects(id)      ON DELETE CASCADE,
    asset_id     TEXT        NOT NULL REFERENCES source_assets(id) ON DELETE CASCADE,
    storage_key  TEXT        NOT NULL,
    content_type TEXT        NOT NULL DEFAULT '',
    max_bytes    BIGINT      NOT NULL DEFAULT 0,
    created_by   TEXT        REFERENCES users(id),
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transcripts (
    id               TEXT PRIMARY KEY,
    workspace_id     TEXT        NOT NULL REFERENCES workspaces(id)    ON DELETE CASCADE,
    project_id       TEXT        NOT NULL REFERENCES projects(id)      ON DELETE CASCADE,
    asset_id         TEXT        NOT NULL REFERENCES source_assets(id) ON DELETE CASCADE,
    language         TEXT        NOT NULL DEFAULT '',
    model            TEXT        NOT NULL DEFAULT '',
    storage_key      TEXT        NOT NULL DEFAULT '',
    word_count       INTEGER     NOT NULL DEFAULT 0,
    duration_seconds DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 같은 자산을 같은 모델/언어로 두 번 전사하지 않는다(비용 절감 + 멱등)
    UNIQUE (asset_id, model, language)
);

CREATE TABLE render_jobs (
    id                 TEXT PRIMARY KEY,
    workspace_id       TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id         TEXT        NOT NULL REFERENCES projects(id)   ON DELETE CASCADE,
    asset_id           TEXT        REFERENCES source_assets(id)       ON DELETE SET NULL,
    project_revision   INTEGER     NOT NULL DEFAULT 1,
    status             TEXT        NOT NULL DEFAULT 'queued'
                       CHECK (status IN ('queued', 'running', 'needs_approval',
                                         'succeeded', 'failed', 'cancelled')),
    stage              TEXT        NOT NULL DEFAULT '',
    progress           DOUBLE PRECISION NOT NULL DEFAULT 0,
    idempotency_key    TEXT        NOT NULL DEFAULT '',
    reused_from_job_id TEXT,
    spec               JSONB       NOT NULL,
    result             JSONB       NOT NULL DEFAULT '{}'::jsonb,
    error_code         TEXT,
    error_message      TEXT        NOT NULL DEFAULT '',
    cancel_requested   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_by         TEXT        REFERENCES users(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX render_jobs_workspace_idx ON render_jobs (workspace_id, created_at DESC);
CREATE INDEX render_jobs_project_idx   ON render_jobs (workspace_id, project_id, created_at DESC);
-- 멱등성을 DB 가 보장한다. 동시에 같은 키로 두 요청이 들어와도 한 건만 남는다.
-- 실패한 작업은 다시 시도할 수 있어야 하므로 제외한다.
CREATE UNIQUE INDEX render_jobs_idempotency_idx
    ON render_jobs (workspace_id, idempotency_key)
    WHERE idempotency_key <> '' AND status <> 'failed';

CREATE TABLE clip_candidates (
    id            TEXT PRIMARY KEY,
    workspace_id  TEXT        NOT NULL REFERENCES workspaces(id)  ON DELETE CASCADE,
    project_id    TEXT        NOT NULL REFERENCES projects(id)    ON DELETE CASCADE,
    job_id        TEXT        NOT NULL REFERENCES render_jobs(id) ON DELETE CASCADE,
    position      INTEGER     NOT NULL DEFAULT 0,
    start_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    end_seconds   DOUBLE PRECISION NOT NULL DEFAULT 0,
    title         TEXT        NOT NULL DEFAULT '',
    viral_score   DOUBLE PRECISION NOT NULL DEFAULT 0,
    reason        TEXT        NOT NULL DEFAULT '',
    selected      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, position)
);

CREATE TABLE render_outputs (
    id               TEXT PRIMARY KEY,
    workspace_id     TEXT        NOT NULL REFERENCES workspaces(id)  ON DELETE CASCADE,
    project_id       TEXT        NOT NULL REFERENCES projects(id)    ON DELETE CASCADE,
    job_id           TEXT        NOT NULL REFERENCES render_jobs(id) ON DELETE CASCADE,
    candidate_id     TEXT        REFERENCES clip_candidates(id)      ON DELETE SET NULL,
    position         INTEGER     NOT NULL DEFAULT 0,
    title            TEXT        NOT NULL DEFAULT '',
    storage_key      TEXT        NOT NULL DEFAULT '',
    uri              TEXT        NOT NULL DEFAULT '',
    width            INTEGER     NOT NULL DEFAULT 0,
    height           INTEGER     NOT NULL DEFAULT 0,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    size_bytes       BIGINT      NOT NULL DEFAULT 0,
    checksum_sha256  TEXT        NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, position)
);

CREATE TABLE job_progress_events (
    id           BIGSERIAL PRIMARY KEY,
    workspace_id TEXT        NOT NULL,
    job_id       TEXT        NOT NULL REFERENCES render_jobs(id) ON DELETE CASCADE,
    stage        TEXT        NOT NULL DEFAULT '',
    percent      DOUBLE PRECISION NOT NULL DEFAULT 0,
    message      TEXT        NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX job_progress_events_job_idx ON job_progress_events (job_id, id);

-- durable queue. Redis 대신 PostgreSQL SKIP LOCKED 를 쓴다.
-- 이유: 작업 상태와 큐가 같은 트랜잭션에 묶여야 "큐에는 있는데 DB 에는 없는" 상태가
-- 생기지 않는다. Redis 로 같은 보장을 만들려면 lease 재수거기를 따로 운영해야 한다.
CREATE TABLE job_queue (
    id               BIGSERIAL PRIMARY KEY,
    job_id           TEXT        NOT NULL REFERENCES render_jobs(id) ON DELETE CASCADE,
    workspace_id     TEXT        NOT NULL,
    queue            TEXT        NOT NULL DEFAULT 'default',
    state            TEXT        NOT NULL DEFAULT 'ready'
                     CHECK (state IN ('ready', 'leased', 'done', 'dead')),
    priority         INTEGER     NOT NULL DEFAULT 0,
    attempts         INTEGER     NOT NULL DEFAULT 0,
    max_attempts     INTEGER     NOT NULL DEFAULT 3,
    available_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_expires_at TIMESTAMPTZ,
    leased_by        TEXT,
    last_error       TEXT        NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 한 작업이 큐에 두 번 살아있지 않게 한다.
CREATE UNIQUE INDEX job_queue_active_idx ON job_queue (job_id) WHERE state IN ('ready', 'leased');
CREATE INDEX job_queue_poll_idx ON job_queue (queue, state, priority DESC, available_at);

CREATE TABLE usage_events (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id   TEXT,
    job_id       TEXT,
    user_id      TEXT,
    event_type   TEXT        NOT NULL,
    quantity     DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit         TEXT        NOT NULL DEFAULT '',
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX usage_events_workspace_idx ON usage_events (workspace_id, occurred_at DESC);

CREATE TABLE cost_events (
    id           TEXT PRIMARY KEY,
    workspace_id TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_id       TEXT,
    provider     TEXT        NOT NULL DEFAULT '',
    resource     TEXT        NOT NULL DEFAULT '',
    quantity     DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit         TEXT        NOT NULL DEFAULT '',
    micro_usd    BIGINT      NOT NULL DEFAULT 0,      -- 1 USD = 1_000_000
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX cost_events_workspace_idx ON cost_events (workspace_id, occurred_at DESC);

-- 크레딧 원장. 잔액은 workspaces 에 캐시하지만 진실은 이 표다.
-- reserve → (commit | release) 로만 움직인다. 실패/취소/중복은 release 된다.
CREATE TABLE credit_ledger (
    id             TEXT PRIMARY KEY,
    workspace_id   TEXT        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    job_id         TEXT,
    entry_type     TEXT        NOT NULL
                   CHECK (entry_type IN ('grant', 'reserve', 'commit', 'release', 'refund', 'adjust')),
    amount         BIGINT      NOT NULL,
    balance_after  BIGINT      NOT NULL,
    reserved_after BIGINT      NOT NULL,
    reason         TEXT        NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 같은 작업에 같은 종류의 원장 기록이 두 번 남지 않는다(중복 차감 방지).
CREATE UNIQUE INDEX credit_ledger_job_entry_idx
    ON credit_ledger (job_id, entry_type) WHERE job_id IS NOT NULL;
CREATE INDEX credit_ledger_workspace_idx ON credit_ledger (workspace_id, created_at DESC);
