# Step 17 Health, Veterinary Care, and Vaccination Report

Date: 2026-10-15

## Outcome

Step 17 is implemented on `feature/step17-health-vaccination`.
The implementation adds complete farm-scoped health workflows without changing
the live `icms_db` schema or records. The live application database remains at
the observed revision `e6f1a2b3c4d5`; its origin remains unknown.

Implementation commit `dd884ccded2b448d83a73eabd958ac0e0a521213` passed
GitHub Backend CI run `38710567722`.

## Architecture

- Health routing is split into encounters, diagnoses, vaccinations, treatments,
  veterinary visits, reminders, audit dependencies, and a composition router.
- SQLAlchemy domain models are in `app/models/health.py`.
- Typed request and response contracts are in `app/schemas/health.py`.
- Shared state validation, scope lookup, and audit helpers are in
  `app/services/health.py`.
- Existing farm membership and permission dependencies protect every endpoint.
- Existing cattle UUIDs are used; no parallel animal identity was introduced.
- Historical reads remain available after cattle lifecycle transitions.
- New clinical actions are rejected for sold, deceased, transferred, or archived
  cattle.

## New database tables

1. `health_encounters`
2. `health_diagnoses`
3. `vaccination_schedules`
4. `vaccination_administrations`
5. `treatment_plans`
6. `medication_administrations`
7. `veterinary_visits`
8. `health_record_corrections`

Composite foreign keys bind health records to the same farm and cattle.
Assigned professionals must reference a member of the same farm, and API checks
also require active membership. Constraints cover chronology, state-dependent
timestamps, positive doses, complete dosage pairs, withdrawal periods, and
controlled correction types. Partial and expression indexes prevent duplicate
active schedules and vaccination replay. Medication events are unique per
treatment and timestamp.

## Migration

- Revision: `f7a2b3c4d5e6`.
- Parent: `e6f1a2b3c4d5`.
- The change is additive and does not rewrite any prior migration.
- Seven PostgreSQL enums and eight tables are created.
- Eight granular health permissions are inserted idempotently.
- Upgrade, metadata comparison, downgrade, and re-upgrade passed in a uniquely
  named disposable schema in `icms_test`.
- The rehearsal produced 23 total tables including `alembic_version`, 32
  permissions, and zero ORM/catalog differences.
- The disposable rehearsal schema was removed afterward.
- No Alembic operation was executed against `icms_db`.

## API surface

Step 17 adds 18 paths and 25 operations:

- Create, list, retrieve, and finalize health encounters.
- Retrieve a consolidated animal health history.
- Create, list, retrieve, and audit diagnosis status transitions.
- Create, list, reschedule, and cancel vaccination schedules.
- Record and list actual vaccination administrations.
- Create and list treatment plans and audit their state transitions.
- Record and list actual medication administrations.
- Create, list, schedule, complete, and cancel veterinary visits.
- Append and list immutable medical correction events.
- Derive upcoming/overdue vaccinations, visits, follow-ups, and treatment work.

The complete API now exposes 50 paths and 70 operations. The OpenAPI digest was
reviewed and updated in the contract test.

## Clinical invariants and history

- Symptoms never imply a confirmed diagnosis automatically.
- Diagnoses distinguish suspected, confirmed, ruled-out, and resolved states.
- Diagnosis transitions are constrained and append audit evidence.
- Encounters can be finalized only once.
- Completed, cancelled, and stopped workflows reject invalid transitions.
- Vaccination schedules and administrations are separate records.
- Administration completes a schedule without deleting schedule history.
- Schedule-linked and standalone vaccination replay is rejected.
- Planned treatments and actual medication events remain separate.
- Withdrawal periods are stored only when explicitly supplied.
- Corrections append snapshots and notes; they do not overwrite original events.
- Reminder computation is deterministic through the optional `as_of` parameter.
- Completed and cancelled items are excluded where appropriate.

## Permissions

The existing `health.view` and `health.manage` permissions remain supported.
Eight new permission codes were added:

- `health.create`
- `health.diagnosis`
- `health.vaccination.manage`
- `health.vaccination.administer`
- `health.treatment.manage`
- `health.medication.administer`
- `health.visit.manage`
- `health.audit.view`

Owners receive all permissions. Farm managers and veterinarians receive the
appropriate predefined health permissions. Workers retain read-only health
access. Existing custom roles with `health.manage` inherit the granular actions,
and custom roles may assign individual new permissions. Inactive users and
members cannot use the module.

## Security controls

- Authorization runs before record lookup or disclosure.
- Every query is constrained by `farm_id`.
- Cross-farm cattle, encounters, schedules, diagnoses, and treatments return
  not-found responses instead of disclosing another tenant's objects.
- Composite PostgreSQL foreign keys prevent cross-tenant inserts below the API.
- Row locks and unique indexes protect state changes and repeated submissions.
- Multi-record operations use one transaction and roll back on conflict.
- Finalized clinical events have no hard-delete endpoint.
- Audit access requires `health.audit.view`.
- No secret, credential, or token is stored in medical records.

## Test evidence

- Previous baseline: 130 tests.
- New Step 17 tests: 22.
- Final result: 152 passed, 0 failed, 0 skipped.
- Migration lifecycle, tenant constraints, seed catalog, rollback, and replay
  protection are tested on PostgreSQL.
- API tests cover chronology, pagination, state transitions, authentication,
  inactive principals, custom roles, cross-farm guessing, reminders, correction
  preservation, and lifecycle history.
- Compilation, imports, OpenAPI generation, and the linear revision chain pass.
- GitHub Actions independently repeated the PostgreSQL CI workflow successfully.

## Limitations and known risks

- Reminders are derived API results; push, email, and background scheduling are
  not implemented.
- No universal vaccine interval or drug withdrawal advice is hard-coded.
- Standardized diagnosis terminology is optional free-form input; no external
  veterinary coding catalog is integrated.
- Medication inventory, purchasing, laboratory results, billing, and attachment
  workflows remain future modules.
- The generic correction target is validated by the API and a database type
  constraint, but polymorphic target existence cannot use one conventional FK.
- The local development JWT key remains below the recommended 32-byte minimum.
- Starlette still emits its known httpx compatibility deprecation warning.
- Production email, object storage, monitoring, shared rate limits, and automated
  backup operations remain deployment work.
