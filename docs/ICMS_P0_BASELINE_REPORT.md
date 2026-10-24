# ICMS P0 Baseline Report

Captured: 2026-10-22 before P0 implementation changes

## Git baseline

- Branch: `feature/step19-react-native`
- Commit: `0f6c861f788c015751bdc07e7ba28cc87893442a`
- Worktree at capture: 63 modified files and 64 untracked paths.
- Modified roots: `.gitignore` (1), `backend` (37), `frontend` (25).
- Untracked roots: `backend` (5), `docs` (3), `frontend` (55), and the pre-existing root file `tatus --short` (1).
- The complete file-level baseline is the `git status --short` output captured at the start of this task. Existing changes are treated as user work and will not be reset, cleaned, or discarded.

## Application and migration baseline

- Checked-in Alembic head: `b7c9d2e4f601`.
- Migration chain is linear from `b9f8ee48d20d` through `b7c9d2e4f601`.
- Generated API: 66 paths and 90 GET/POST/PUT/PATCH/DELETE operations.
- SQLAlchemy metadata: 27 application tables.
- Authentication endpoints: register, login, current-user profile, email verification, verification resend, forgot password, and reset password.

## Protected database baseline

Inspection used an explicit read-only transaction.

- Database: `icms_db` on local PostgreSQL port 5432; role `icms_app`.
- Alembic revision: `a8b3c4d5e6f7`.
- Physical tables in `public`: 27, including `alembic_version`.
- `users.token_version`: absent.
- `password_reset_tokens`: absent.
- Existing rows counted without reading user content: 2 users and 2 farms.
- Result: the protected schema/application mismatch is confirmed. No protected database change has been made.

## Authentication and email baseline

- Environment: development.
- Email mode: console.
- Verification URL points to `http://localhost:8765/api/v1/auth/verify-email`, while the verification endpoint is POST-only.
- The frontend verification route does not read a deep-link/query token; it supports manual entry only.
- Reset URL points to the frontend reset-password route and its token flow is implemented.
- No SMTP sender exists. Non-console production delivery is rejected.
- Registration, resend, invitations, and password reset already call the shared email-sender abstraction.

## CI and deployment baseline

- Backend CI asserts stale values: 63 paths, 87 operations, 26 tables, and head `a8b3c4d5e6f7`.
- Frontend CI runs tests, Expo dependency checks, Expo Doctor, and web/Android exports.
- No backend Dockerfile, staging Compose definition, production health/readiness endpoints, backup/restore scripts, or deployment runbook was present.
- Rate limiting is process-local. No shared Redis limiter is configured.

## Fresh test baseline

- Backend with a credential-safe, isolated `icms_test` connection and workspace-local pytest temp directory: **214 passed** in 30.54 seconds.
- Backend warning: Starlette's current TestClient/httpx integration is deprecated upstream.
- Pytest cache warning: sandbox denied writes to `backend/.pytest_cache`; test execution and results were unaffected.
- Frontend structure suite: **13 passed**.
- Frontend Jest suite: **297 passed across 21 suites**.
- An initial backend invocation without `TEST_DATABASE_URL` produced 16 unit passes and 198 skips; it is recorded as an incomplete diagnostic run and was superseded by the 214-test isolated PostgreSQL run.

## P0 entry decision

Code-only work and isolated database validation may proceed. Any upgrade, rollback, or other mutation of `icms_db` remains blocked pending the explicit approval gate defined in the task.
