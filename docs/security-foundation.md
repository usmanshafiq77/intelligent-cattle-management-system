# ICMS security foundation

This branch adds concurrency, ownership, abuse-prevention, email-verification,
and test foundations without applying a migration or changing existing data.

## Database invariants and migration review

`c3a1f5e8d9b2_security_foundation.py` is additive. Before creating constraints,
it aborts the transaction if it finds:

- more than one `PENDING` invitation for the same farm and case-insensitive email;
- an invitation carrying `FARM_OWNER`;
- an inactive owner membership;
- multiple active owner memberships for one farm; or
- a `farms.owner_id` without the matching active owner membership.

The migration never deletes, merges, expires, or rewrites existing records.
Resolve any reported rows only after manual review. In particular, decide which
duplicate invitation remains pending and explicitly revoke or expire the others.

PostgreSQL enforces at most one pending invitation per farm and normalized email,
at most one active owner membership per farm, active status for owner memberships,
and rejection of owner-role invitations. `farms.owner_id` remains authoritative.
Matching that ID to the owner membership, and guaranteeing at least one owner,
are enforced by application transactions and authorization dependencies because
a simple cross-table constraint would introduce unsafe circular insert behavior.
No ownership-transfer endpoint is introduced. A future transfer must demote the
old owner membership, update `farms.owner_id`, and create or promote the new
active owner membership in one database transaction.

Expired pending invitations are changed to `EXPIRED` in the same transaction
that creates a replacement. The partial unique index then arbitrates concurrent
requests; the losing request receives HTTP 409.

## Existing users and email verification

The migration adds nullable `users.email_verified_at`. Existing users remain
active and can continue to log in, but they are intentionally not marked as
verified. They can use `POST /api/v1/auth/verification/resend`, then submit the
one-time token to `POST /api/v1/auth/verify-email` as JSON:

```json
{"token": "token-from-the-delivery-channel"}
```

Verification and invitation tokens are generated with `secrets`, stored only as
SHA-256 hashes, expire, and are single-use. The invitation acceptance guard also
requires the authenticated user's normalized email to match a verified identity.

## Invitation acceptance

`POST /api/v1/invitations/accept` requires an active authenticated user and a
verified email address. The raw token is hashed before lookup, and the matching
invitation row is locked until the transaction completes. Acceptance also locks
the farm, verifies that the inviter is still the authoritative active owner,
rejects owner-role elevation and every pre-existing membership state, creates an
ACTIVE membership with the invitation's exact role, and marks the invitation
ACCEPTED with a UTC timestamp. Membership creation and token consumption commit
together, so concurrent replays produce exactly one successful request.

Invitation creation uses the existing email-delivery abstraction. Automated
tests use the in-memory sender, local development may use console delivery, and
raw invitation tokens are omitted from API responses outside local/test
environments. A production email provider remains deployment configuration.

In local development, `EMAIL_DELIVERY_MODE=console` writes the one-time
verification link to local server logs. This mode is refused outside the
`development` or `local` environment and must never be used for production logs.
Automated tests replace it with an in-memory sender. A production email provider
must implement the `EmailSender` interface; no SMTP credentials are included.

## Rate limiting

Login, registration, and verification resend use configurable fixed-window
limits. Limits are applied independently to the direct client IP and a hash of
the normalized email, preventing a single client from bypassing throttling by
rotating claimed accounts. Responses are generic HTTP 429 errors with
`Retry-After`.

The included limiter is process-local. It is appropriate for one local server
process only. Multiple workers or production replicas require a shared store or
an equivalent trusted gateway limit. Proxy headers are deliberately not trusted
by this implementation; configure the deployment's trusted proxy layer before
deriving client identity from forwarded headers.

## Isolated PostgreSQL tests

Install `requirements-dev.txt` and set `TEST_DATABASE_URL` to a dedicated
PostgreSQL database whose name starts with `test_` or ends with `_test`.

The test harness refuses non-PostgreSQL URLs, `icms_db`, and database names that
do not clearly identify a test database. It verifies `current_database()` before
creating a uniquely named disposable schema. Integration tests are skipped when
this variable is absent; SQLite is never substituted. The harness drops only
that generated schema during teardown. Tests use transactions and do not send
real email.

Example PowerShell session (use your own test-only credential):

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost/icms_test'
pytest
```

Do not run the migration or tests against `icms_db`.
