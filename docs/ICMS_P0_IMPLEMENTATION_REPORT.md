# ICMS P0 Implementation Report

Date: 2026-10-23
Branch: `feature/step19-react-native`
Starting commit: `0f6c861f788c015751bdc07e7ba28cc87893442a`

## Executive result

The safe code, CI, isolated-database, backup, email, and deployment work is implemented and verified. The protected `icms_db` upgrade is intentionally not performed: it remains at `a8b3c4d5e6f7` pending explicit approval to apply `b7c9d2e4f601`. No real external email was sent and nothing was deployed.

Current automated result:

- Backend: **226 passed**.
- Frontend architecture: **13 passed**.
- Frontend Jest: **299 passed across 21 suites**.
- Expo Doctor: **21/21 checks passed**.
- Expo dependency compatibility: passed.
- Web production export: passed.
- Android production export: passed.

## Baseline

The pre-change facts and dirty-worktree inventory are recorded in `docs/ICMS_P0_BASELINE_REPORT.md`. The task began with 63 modified files and 64 untracked paths. Existing work was preserved.

## P0.1 — database migration compatibility and authentication

Initial defect:

- Application head was `b7c9d2e4f601`; protected `icms_db` was `a8b3c4d5e6f7`.
- `users.token_version` and `password_reset_tokens` were absent from `icms_db`.

Changes and verification:

- Added a migration contract test that verifies the full revision chain and expected ORM table names.
- Added a dedicated password-reset migration lifecycle test.
- The lifecycle test creates an isolated schema, migrates to `a8b3c4d5e6f7`, inserts an existing user and farm, upgrades to `b7c9d2e4f601`, verifies the default, table, foreign key, unique constraint, normal index, partial unique index, and data preservation, rolls back to `a8b3c4d5e6f7`, verifies core data remains, and upgrades again.
- Added readiness revision enforcement. `/api/v1/health` remains liveness; `/api/v1/health/db` returns 503 when the database is reachable but behind the application migration head.
- Generated and verified a protected logical backup without modifying the database.
- Restored that archive into a disposable isolated schema in `icms_test`, verified revision and table count, and removed the schema.
- Full authentication, farm isolation, RBAC, cattle, health, and milk regression tests passed.

Evidence:

- Backup: `D:\ICMS_Project\backups\icms_db_20261022_234512_743.dump`
- Size: 108,454 bytes.
- SHA-256: `D3AF0004F1B827DD0C41C3EEB8D7E7398BF38E2490B9246CF5A2F8FF1A796FF6`.
- `pg_restore --list`: passed.
- Restore validation: revision `a8b3c4d5e6f7`, 27 physical tables.
- Remaining disposable restore schemas: zero.
- Current protected readiness: 503 `Database migration required`.

Remaining risk:

- The current code is not ready against `icms_db` until the protected upgrade is approved and applied.
- The migration briefly requires PostgreSQL DDL locks. Expected maintenance impact is short for the current two-user/two-farm database, but an approved window remains required.
- Migration downgrade removes reset tokens and the token-version column. Backup restoration is the preferred recovery path after real use begins.

Status: **BLOCKED** only at the protected-database approval boundary. All preparation and isolated verification are **COMPLETE**.

## P0.2 — verification links, SMTP, and recovery delivery

Initial defects:

- Verification emails linked to a POST-only API URL.
- The frontend did not read the verification deep-link token.
- Only local console delivery existed.
- Invitation email delivery exposed only a raw token rather than an actionable frontend link.

Changes:

- Verification URLs now default to `{FRONTEND_PUBLIC_URL}/auth/verify-email`.
- The Expo route captures the query token, removes it from the route parameters, and automatically submits it once to the existing POST endpoint.
- Manual token entry, resend, expired/invalid/reused handling, and network feedback remain available.
- Invitation links now target the frontend acceptance route and prefill the token; acceptance still requires deliberate confirmation.
- Added an SMTP sender supporting STARTTLS or implicit TLS, authenticated SMTP, connection timeouts, bounded retries for transient failures, non-retryable authentication/recipient failures, safe text templates, sanitized exceptions, and logs that do not contain tokens.
- Registration, verification resend, invitations, and password reset continue through the existing sender abstraction.
- Console delivery remains restricted to local/development environments.
- Production configuration requires SMTP mode, HTTPS public URLs, explicit origins, and a non-placeholder JWT secret of at least 32 characters.

Tests:

- SMTP delivery, STARTTLS, login, template URLs, timeout retry, permanent failure handling, token-log redaction, invalid configuration, and production configuration tests pass.
- Existing delivery-failure, resend, reset, invitation, expiration, reuse, and enumeration-safe tests pass.
- Frontend automatic verification and invitation-prefill tests pass.

Durable outbox decision:

- A database outbox was not added to this P0 migration because it would introduce another protected schema change and the agreed staging baseline is a single API instance with synchronous bounded retry and explicit delivery status.
- This means a provider outage after token creation requires the existing resend/reissue workflow. A durable outbox is required before claiming high-availability or guaranteed delivery in a multi-instance production deployment.

Manual dependencies:

- Approved SMTP provider credentials or a Gmail App Password.
- Verified sender identity and final public HTTPS frontend URL.
- A real mailbox delivery test requires explicit approval and was not performed.

Status: SMTP and deep-link implementation **COMPLETE**; external-provider activation **BLOCKED** by credentials and real-send approval.

## P0.3 — CI, security, deployment, and recovery

CI changes:

- Replaced stale inline CI counts with reviewed OpenAPI, exact ORM table-set, and Alembic-chain contract tests.
- API contract remains 66 paths and 90 operations with a canonical SHA-256 snapshot.
- ORM contract is the exact set of 27 application tables.
- Alembic contract ends at `b7c9d2e4f601`.
- Password-reset migration lifecycle is now part of the CI migration group.

Security changes:

- Staging/production/test enforce a JWT secret of at least 32 characters; production rejects known placeholders.
- Production requires HTTPS CORS and action URLs plus SMTP delivery.
- Added request IDs, request completion logging, JSON log mode, `nosniff`, frame denial, no-referrer policy, auth no-store policy, and production HSTS.
- Readiness fails closed on database revision drift.
- Reverse-proxy trust remains an explicit Uvicorn `FORWARDED_ALLOW_IPS` deployment setting; wildcard trust is prohibited by documentation.
- Existing farm isolation, server-side RBAC, request validation, and rate limits remain unchanged and pass regression tests.

Deployment changes:

- Added non-root backend and frontend Dockerfiles.
- Added an nginx configuration for the web export.
- Added `compose.staging.yml` with PostgreSQL, backend, frontend, persistent database/media volumes, health checks, and a manual profile-gated migration service.
- Normal backend startup never runs Alembic.
- Added a staging environment template with no real secrets.
- Compose structure was parsed and validated locally. Docker itself is not installed in this execution environment, so image builds and container runtime checks remain external.

Backup/recovery changes:

- Added unique, non-overwriting PostgreSQL custom-format backup tooling with archive verification.
- Retention is report-only; no unattended deletion occurs.
- Added disposable database or isolated test-schema restore validation.
- Added media archive tooling and a disposable-fixture validation.
- The actual `backend/uploads` tree contains pre-existing pytest directories that this account cannot read recursively, so a full current-media archive is blocked until permissions are repaired.

Dependency review:

- Python `pip check`: passed.
- Expo was updated within SDK 57 to `expo` 57.0.31 and `expo-router` 57.0.29, as required by Expo compatibility checks.
- `npm audit --omit=dev` reports 56 transitive findings (48 high, 8 moderate after the patch update), primarily through Expo/Metro/Jest dependency chains.
- npm's proposed broad remediation requires breaking changes, including incompatible Expo/Jest replacements. `--force` was not used. This remains an upstream-compatible upgrade task, not a silently forced P0 change.
- Process-local rate limiting remains suitable only for a single API process. A shared Redis-backed limiter is still required for multi-worker/multi-host enforcement.

Status: CI contract repair **COMPLETE**; staging configuration **PARTIAL** pending Docker runtime validation; production operations **PARTIAL** pending TLS/proxy/monitoring infrastructure, media permission repair, shared rate limiting where scaled, and upstream dependency remediation.

## Significant files changed or created

Backend:

- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/migrations.py`
- `backend/app/main.py`
- `backend/app/services/email_delivery.py`
- `backend/.env.example`
- `backend/Dockerfile`
- `backend/.dockerignore`
- `backend/tests/test_architecture_contract.py`
- `backend/tests/test_email_delivery.py`
- `backend/tests/test_health_readiness.py`
- `backend/tests/test_password_reset_migration.py`
- `backend/tests/test_cors.py`

Frontend:

- `frontend/app/auth/verify-email.jsx`
- `frontend/app/invitations/accept.jsx`
- `frontend/src/features/auth/screens/VerificationScreen.jsx`
- `frontend/src/features/staff/screens/AcceptInvitationScreen.jsx`
- `frontend/tests/profile-verification.test.jsx`
- `frontend/tests/staff-invitations.test.jsx`
- `frontend/tests/project-structure.test.mjs`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/Dockerfile`
- `frontend/.dockerignore`
- `frontend/nginx.conf`

CI, deployment, backup, and documentation:

- `.github/workflows/backend-ci.yml`
- `compose.staging.yml`
- `deploy/.env.example`
- `scripts/backup-postgres.ps1`
- `scripts/validate-postgres-restore.ps1`
- `scripts/backup-media.ps1`
- The six P0 documents in `docs/`.

Some listed application/test files were already modified or untracked at baseline; changes were applied in place without discarding existing work.

## Test evidence

- Backend full isolated PostgreSQL run: 226 passed in 35.03 seconds.
- Frontend: 13 structural checks passed; 299 Jest tests passed in 21 suites.
- Focused backend P0 run: 16 passed.
- Focused frontend verification/invitation run: 108 passed.
- Dedicated password-reset migration lifecycle: 1 passed.
- Expo dependency compatibility: passed.
- Expo Doctor: 21/21 passed.
- Web export: passed, 904 modules bundled.
- Android export: passed, 1,367 modules bundled.
- Python source compilation: passed for 106 files using an in-memory compile
  check. The ordinary bytecode-writing `compileall` invocation could not replace
  pre-existing locked files in `backend/tests/__pycache__`.
- Python package consistency: passed.
- Compose YAML structural validation: passed.

Warnings:

- Starlette warns that its current `httpx` TestClient integration is deprecated upstream.
- The sandbox cannot write `backend/.pytest_cache`; workspace-local test temp directories were used and results were unaffected.
- Pre-existing locked test bytecode caches prevent a write-based `compileall`
  pass; source compilation itself succeeds without cache writes.

## Final P0 checklist

- Protected backup created and catalog verified: **COMPLETE**.
- Backup restore validation: **COMPLETE** using an isolated schema in `icms_test`.
- Password-reset migration upgrade/downgrade test: **COMPLETE**.
- Protected `icms_db` migration: **BLOCKED** pending explicit approval.
- Authentication regression verification: **COMPLETE** in isolated tests; protected smoke test awaits migration.
- Verification deep-link journey: **COMPLETE**.
- SMTP implementation and mocked tests: **COMPLETE**.
- Real provider configuration/send: **BLOCKED** pending credentials and approval.
- Backend CI architecture contracts: **COMPLETE**.
- Security configuration/readiness/logging baseline: **COMPLETE** for code; infrastructure controls remain **PARTIAL**.
- Docker/Compose definitions: **COMPLETE** as configuration; runtime validation **BLOCKED** because Docker is unavailable locally.
- PostgreSQL backup tooling: **COMPLETE**.
- Media backup tooling: **COMPLETE**; current media-tree backup **BLOCKED** by pre-existing filesystem permissions.
- Full regressions and Expo exports: **COMPLETE**.
