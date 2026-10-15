# ICMS Pre-Step-17 Readiness Report

Date: 2026-10-15 (Asia/Karachi)

## Scope and safety

- This review is the final Step 16.5 verification checkpoint.
- Step 17 was not started.
- `icms_db` was inspected read-only and was not migrated, stamped, or altered.
- Revision `e6f1a2b3c4d5` was already present when this review began.
- The origin of that migration state is unknown; this report does not claim Codex applied it.
- Recovery database `icms_recovery_20261015_49a8dbe7da61` remains intact.
- The verified external backup remains intact.
- Backup SHA-256 is `AF506B55981356F2B7D98DAC3F8FA31BEAD7B577D93ECCA8C81ECF221AA17649`.

## Live database verification

- Connected database: `icms_db`.
- Connected role and database owner: `icms_app`.
- Observed Alembic revision: `e6f1a2b3c4d5`.
- Application tables: 14; total public tables including `alembic_version`: 15.
- Live catalog totals: 116 columns, 152 constraints, 47 indexes, and 10 enum types.
- All inspected public relations are owned by `icms_app`.
- A clean Step 16.5 schema was independently built in a UUID-named `icms_test` schema.
- Normalized table, column, constraint, index, and enum fingerprints were compared.
- Differences between the live and independently built catalogs: none.
- The audit schema was removed after comparison; no audit or test schema was left behind.

## Expected application tables

- `users`, `farms`, `farm_members`, and `invitations`.
- `email_verification_tokens`.
- `permissions`, `farm_custom_roles`, `farm_role_permissions`, and `farm_member_roles`.
- `breeds`, `cattle`, `cattle_media`, `cattle_lifecycle_events`, and `cattle_weight_records`.

## Data preservation and seed verification

- Original counts remain: 1 user, 1 farm, 1 membership, and 1 invitation.
- Each original row was compared with the recovery database over all common columns.
- Counts and SHA-256 row digests matched for all four tables.
- No sensitive record values were printed or copied into this report.
- RBAC permission count: 24; the complete expected code set is present.
- Breed count: 9; all expected deterministic seed rows are present and active.
- No application record was inserted, updated, or deleted during verification.

## Application checks

- Application configuration resolves to `icms_db` for normal local operation.
- A read-only engine connection verified database, role, revision, and `SELECT 1`.
- Backend compilation completed successfully.
- Application and model imports completed successfully.
- SQLAlchemy metadata contains 14 application tables.
- OpenAPI generation contains 32 paths and 45 operations.
- The local environment is configured as `development`.

## Automated tests

- Test target was verified as exactly `icms_test`, owned by `icms_app`.
- The harness rejected use of `icms_db` and selected a UUID-named disposable schema.
- Complete result: 130 passed, 0 failed, 0 skipped.
- Runtime: 18.31 seconds.
- No disposable audit or test schemas remained after completion.
- The run emitted one Starlette/httpx deprecation category.
- It also revealed that the local development JWT key is below PyJWT's 32-byte recommendation.
- No secret value was displayed, logged in this report, or committed.

## Repository and CI

- Branch: `chore/backend-maintenance-ci`.
- Verified local and remote SHA: `4e282e48ddf0ddefc8dd911041197456306c879e`.
- Worktree was clean before this report was created.
- Latest applicable Backend CI run: `38631799478`.
- CI revision: `e354dc2d0bd1282eedf758606259d613e30c3aac`.
- CI conclusion: successful.
- The current head adds documentation only, outside the workflow's backend path filter.
- Local `.env` is ignored; only the placeholder `backend/.env.example` matches tracked sensitive-file names.

## Problems and recommendation

- No database schema difference, lost business record, failed test, or skipped integration test was found.
- Migration provenance remains unknown and should remain documented as such.
- Rotate the local development JWT key to at least 32 random bytes before shared or production use.
- Consider enforcing a minimum JWT key length in validated configuration in a future security change.
- The Starlette/httpx deprecation should be addressed during dependency maintenance.
- These two warnings do not block Step 17 development or affect the verified database schema.
- Independent recommendation: Step 17 can safely begin after this checkpoint is accepted.
- Production deployment should remain gated on replacing the undersized JWT key.
