# Step 18 Milk Production Management Report

Date: 2026-10-15
Branch: `feature/step18-milk-production`
Source commit: `7065006`
CI workflow commit: `3b423ca`
Migration: `a8b3c4d5e6f7` (parent `f7a2b3c4d5e6`)

## Status

Step 18 source implementation, isolated PostgreSQL verification, backup restore
rehearsal, and approved live migration are complete. `icms_db` is verified at
revision `a8b3c4d5e6f7`. Read-only and transaction-rolled-back write-path
application smoke checks pass.

## Implemented architecture

The milk domain is farm-scoped and split across routers, schemas, models, and a
shared business-rule service. It reuses the existing authentication, active farm
membership, custom RBAC, cattle UUIDs, and PostgreSQL transaction model.

Four additive tables are introduced:

- `milk_lactations`: sequence, date range, lifecycle status, actor, and timestamps.
- `milking_sessions`: lactation-scoped individual production facts.
- `milk_quality_measurements`: optional timestamped composition and sample data.
- `milk_record_corrections`: append-only original/effective correction provenance.

Composite foreign keys prevent farm/cattle/lactation/session mismatches. Partial
and ordinary unique indexes enforce one active lactation and unique animal/date/
session identities. Cattle-row and lactation-row locks coordinate competing
lactation and session writes. Bulk creation validates all items and commits once.

## Business rules

- Milk production is accepted only for active female animals categorized as
  `COW`; cattle and buffalo species remain supported by the shared cattle model.
- Historical reads remain available after sale, transfer, death, or archive, but
  new production facts are blocked for final lifecycle states.
- Lactation sequence numbers are positive and unique per animal. Periods cannot
  overlap. Transitions are `ACTIVE -> DRY -> COMPLETED` or
  `ACTIVE -> COMPLETED`, with chronological and latest-session safeguards.
- Liters (`L`) are the only accepted unit. Volume is stored as `NUMERIC(12,3)`.
  Zero is a deliberate valid observation; missing records are never treated as
  confirmed zero production.
- `MORNING` and `EVENING` use their canonical session codes. `ADDITIONAL` permits
  a distinct normalized custom code, allowing legitimate extra collections.
- Quality percentages accept 0 through 100. Density must be positive,
  temperature cannot be below absolute zero, and somatic cell count is
  nonnegative. No API claims that a sample is safe or laboratory-certified.
- Corrections cannot alter identity fields. Each event stores the prior effective
  values and a complete replacement state, so the latest event resolves
  deterministically while the original fact remains unchanged.

Calendar aggregation uses the stored `milking_date`; timestamps must be timezone
aware. API decimals are serialized without floating-point accumulation.

## API surface

All routes use `/api/v1/farms/{farm_id}/milk`:

- `POST/GET /lactations`
- `GET /lactations/active`
- `GET /lactations/{lactation_id}`
- `POST /lactations/{lactation_id}/transition`
- `POST/GET /sessions`
- `POST /sessions/bulk`
- `GET /sessions/{session_id}`
- `POST/GET /quality`
- `GET /quality/{quality_id}`
- `POST/GET /corrections`
- `GET /analytics/production`
- `GET /analytics/breakdown`
- `GET /analytics/dataset`

Step 18 adds 13 paths and 17 operations. The complete contract has 63 paths and
87 operations, pinned by SHA-256
`6199c4095b695675714e06923a73e68d82d28889be79ed6025dd853252842014`.

## RBAC

Existing `milk.view`, `milk.record`, and `milk.manage` compatibility is retained.
Five granular codes bring the catalog from 32 to 37 permissions:

- `milk.lactation.manage`
- `milk.quality.manage`
- `milk.correct`
- `milk.analytics.view`
- `milk.bulk.create`

Owners have all permissions. Managers receive operational management. Workers
retain routine view/record/bulk access. Veterinarians have default read access.
Custom roles can receive individual milk permission codes. Active membership and
farm scoping are enforced before object disclosure.

## Analytics and AI data readiness

Daily, weekly, and monthly recorded totals use latest effective corrected
volumes. APIs expose session and animal breakdowns, recorded-animal averages,
highest/lowest recorded producers, empty results, and an explicit
`missing_records_are_zero: false` marker.

The authorized dataset endpoint supplies currently observable features: animal
UUID, species, breed UUID, birth date, lactation number, days in milk, date,
session kind, effective volume, and available quality values. Missing quality is
preserved as null and identified through `observation_complete`. Feed, weather,
pregnancy, calving, and training labels are not fabricated. The endpoint is a
data-extraction foundation, not a trained model or prediction claim.

## Verification evidence

- Canonical environment: Python 3.13.14; `pip check` reports no broken packages.
- Python compilation: passed.
- Alembic chain: one linear head, `a8b3c4d5e6f7`.
- Isolated migration: upgrade, ORM/catalog parity, constraint test, downgrade,
  existing-data preservation, and re-upgrade passed in a unique `icms_test`
  schema.
- Final release tests: 184 passed, 0 failed, 0 skipped in 40.75 seconds.
- Warnings: one known Starlette/httpx test-client deprecation.
- OpenAPI: 63 paths, 87 operations.
- SQLAlchemy metadata: 26 tables (four new milk tables).
- Local and remote branch SHA: `3b423ca4d3492f26480e31737243646a6045548f`.

The concurrency suite proves that two independent PostgreSQL transactions using
the production lock convention serialize overlapping lactation creation. It is
not a simultaneous HTTP-load test.

## Backup and deployment checkpoint

`D:\ICMS_Backups\icms_db_pre_step18_20261015_180954.dump` exists outside the
repository, is a readable PostgreSQL custom archive, is 88,821 bytes, and has
SHA-256 `96C1DBDC3E795DF6F5B19D85067EA150CA985852CD07144E2936600C2D05E44F`.
A separate-database restore completed with `pg_restore` exit code 0 and no SQL
errors. The verified restore database is
`icms_recovery_step18_20261015_184835_4e443a4362ab`; it remains at revision
`f7a2b3c4d5e6` and has source parity across 23 tables, 241 columns, 77 indexes,
68 enum labels, all table row counts, 32 permissions, and nine breeds. It
contains 1 user, 1 farm, 1 membership, 1 invitation, and 0 cattle.

The first database `icms_recovery_step18_20261015_184817_16fcbc99fdbe` was
created but remained empty because PowerShell treated verbose restore status as
a shell error before restoration began. It contains zero public tables and was
preserved rather than deleted. No existing database was reused.

PostgreSQL renders one restored, pre-existing health check constraint with an
equivalent cast expression (`varchar[]::text[]` versus per-element `::text`). Its
name and allowed values are identical; all other constraint definitions are
textually identical. Credential-file contents were never read or exposed.

Pre-migration read-only live checks found revision `f7a2b3c4d5e6`, 23 tables, 32 permissions,
and aggregate counts of 1 user, 1 farm, 1 membership, 1 invitation, and 0 cattle.
There were no other non-idle `icms_db` sessions during the check.

The zero-cattle count differs from an earlier Step 17 statement reporting one
animal. Repository evidence cannot establish whether that historical count was
valid; both the source and independently restored 18:09 backup contain zero.
This audit made no business-data changes, so the difference is recorded as
historically unverified rather than asserted as data loss.

Final preflight confirmed database `icms_db`, schema `public`, owner `icms_app`,
the required schema/table privileges, no other non-idle session, no waiting
database lock, and intended next revision `a8b3c4d5e6f7`. The explicitly approved
upgrade then completed under transactional DDL without errors.

Postflight verified revision `a8b3c4d5e6f7`, 27 public tables, all four milk
tables, 37 permissions, all five new milk codes, all expected milk columns,
constraints, indexes, and enum labels, unchanged existing record counts, and
zero rows in every milk table. SQLAlchemy-to-database metadata drift is zero.
Application connectivity and read-only HTTP checks passed for root, service
health, database health, lactations, sessions, quality, corrections, production
analytics, and production breakdown.

The approved write-path smoke test used two uniquely marked synthetic farms, one
synthetic cow, one lactation, two bulk sessions, one additional session, one
quality sample, and one correction. It verified authentication rejection, owner
access, farm isolation, lifecycle transitions, atomic bulk entry, individual
entry, effective corrected volume, correction history, and a corrected analytics
total of 22.500 L. Every endpoint used one connection and savepoint-backed
session inside an outer transaction. The outer transaction remained active and
was rolled back in `finally`; an independent connection then confirmed zero
table-count differences and zero remaining synthetic records.

## Known limitations

- Analytics and dataset routes perform latest-correction lookups per result, an
  N+1 performance concern for large exports. Batch/subquery optimization is P1.
- Database concurrency is covered, but HTTP-level concurrent request testing is
  not yet present.
- `observation_complete` means a quality sample exists; it does not mean every
  optional quality field is populated or laboratory-verified.
- The optional `.venv_diagnostic` has a stale inaccessible interpreter reference;
  final verification used the healthy canonical Python 3.13.14 `backend/.venv`.
- Production JWT secret strength remains an operational warning. No secret was
  rotated during Step 18.
- Production email, shared rate limiting, object storage, monitoring, automated
  backup retention, and stronger secret operations remain platform work.

No migration was run against `icms_db`, and no backup, recovery database,
credential, or business record was modified during this audit.
