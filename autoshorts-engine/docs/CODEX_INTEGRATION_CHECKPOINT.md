# Integration handoff checkpoint — 2026-09-16

Base: `270e87d5569afceba92d27a96b0d1912f224cb6b` (Claude Phase 2 WIP handoff).
Working branch: `codex/shorts-studio-integration`.

## Changes verified here

- LocalStorage now validates path ancestry rather than a string prefix. A sibling
  directory named media-other is no longer accepted under a root named media.
- Added regression coverage for read, URI, write, symlink escape, and valid nested
  storage roundtrip. Filesystem roots must still be worker-controlled; this is not
  protection against a privileged process swapping symlinks concurrently.
- Destructive PostgreSQL test fixtures no longer fall back to the application
  database URL. Only AUTOSHORTS_TEST_DATABASE_URL is accepted. This must point to
  a disposable database: the fixtures drop public schema and truncate tables.
- Added a regression check proving the production URL fallback is disabled.

## Verification

`python -m pytest -o addopts='' -q --disable-warnings`:
715 passed, 137 skipped, 2 warnings. 136 skips require PostgreSQL and one requires
google-auth. PostgreSQL is not installed/configured in this environment. These
skips are NOT evidence that tenancy, queue concurrency, or credit accounting work.
Storage smoke checks and git diff --check also passed.

## Updated assessment

Claude added a SaaS auth layer, PostgreSQL repositories, queue, worker and credit
ledger. Do not reimplement those based on the earlier Phase 0 audit. The old engine
API remains separate; use the new SaaS API as the basis for further review.
The handoff still marks Phase 2 WIP: actual engine E2E, separate API/worker process
continuity, hard timeouts and real S3 upload validation remain incomplete.

## Next gate

1. Provision a disposable PostgreSQL test database and rerun DB tests.
2. Verify real FFmpeg output through separate API and worker processes, documenting
   cached transcription separately from actual STT verification.
3. Review factory ZIP vs latest master changes before selecting the source version.
4. Add a generate adapter alongside the repurpose adapter, with publishing disabled
   until explicit artifact approval and per-customer credential boundaries exist.

No factory private source was copied into this public repository. No production
branch was merged, scheduler changed, video uploaded, or billable AI called.
This checkpoint does not claim that the two programs are integrated or launch-ready.
