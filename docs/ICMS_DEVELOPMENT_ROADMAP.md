# ICMS Development Roadmap

## P0 status update - 2026-10-23

- **P0.1 - prepared; protected upgrade awaiting approval.** Backup creation,
  archive restore validation, migration review, readiness drift detection, and
  isolated upgrade/downgrade/re-upgrade testing are complete. `icms_db` is still
  at `a8b3c4d5e6f7`, so the protected migration and its smoke tests remain open.
- **P0.2 - implementation complete.** Frontend verification deep links consume
  and clear their token, verification is submitted once, and manual/resend/error
  paths remain covered. A real mailbox journey is part of the P0.3 activation
  gate.
- **P0.3 - code complete; external activation blocked.** SMTP/TLS, retry policy,
  sanitized failures, and verification/invitation/reset templates are tested.
  Approved provider credentials and permission to send real messages are still
  required. A durable outbox remains a production reliability enhancement.
- **P0.4 - complete.** CI runs executable API, ORM-table, Alembic-chain, and
  password-reset migration contracts against the current code.
- **P0.5 - local baseline complete; environment integration partial.** Container
  manifests, manual migration gating, health checks, security headers, structured
  logging, and database/media backup tooling are present. Docker runtime testing,
  hosted TLS/proxy configuration, monitoring, secret management, durable media,
  and remediation of breaking-only transitive npm audit findings remain open.

Roadmap date: 2026-10-22
Basis: evidence in `ICMS_PROJECT_AUDIT.md`
Estimates: focused engineering time, excluding approval queues and external procurement

## Delivery principles

1. Restore a deployable, recoverable authentication baseline before expanding scope.
2. Finish end-to-end journeys for backend features already built before starting new modules.
3. Keep PostgreSQL changes migration-driven and test every migration in an isolated schema first.
4. Keep backend permissions authoritative; frontend guards improve experience but never replace API enforcement.
5. Do not start model training until data ownership, labeling, quality, evaluation, and deployment criteria exist.

## P0 — release blockers

### P0.1 Safely reconcile the protected database with the current migration head

- Backend: add startup/preflight documentation that reports, but does not silently repair, migration drift.
- Frontend: add a controlled maintenance/unavailable message if the API cannot serve due to migration state.
- Database: back up `icms_db`; verify restore; review `b7c9d2e4f601`; apply `a8b3c4d5e6f7 -> b7c9d2e4f601` during an approved window; verify `users.token_version`, reset-token constraints/indexes, and Alembic head.
- Dependencies: PostgreSQL/Alembic access and explicit operator approval.
- Estimate: 0.5–1 day after approval.
- Acceptance: backup is restorable; migration succeeds; login, `/auth/me`, forgot/reset, old-token rejection, and normal farm access pass against the protected environment; no unrelated schema/data changes occur.

### P0.2 Repair the verification link end to end

- Backend: generate a frontend deep link, or provide a safe GET confirmation bridge with a final POST action; keep tokens out of normal analytics/logging.
- Frontend: consume the verification route token, show explicit confirmation, submit the POST request, and handle expired/already-used states.
- Database: none expected.
- Dependencies: verified frontend public base URL.
- Estimate: 0.5–1 day.
- Acceptance: a newly registered user clicks the delivered link on web/mobile, verifies once, receives clear status, and can log in; reused and expired links are safe and understandable.

### P0.3 Add real Gmail/SMTP delivery with production-safe configuration

- Backend: implement a provider adapter, TLS, timeouts, redacted structured failures, retry policy, and provider health diagnostics while retaining console mode for local development.
- Frontend: surface generic delivery success and safe retry guidance without account enumeration.
- Database: optional durable delivery/outbox table if retries must survive process restarts; preferred for production.
- Dependencies: Gmail Workspace/SMTP or approved mail provider credentials, sender/domain policy, secret storage.
- Estimate: 1–3 days depending on outbox scope.
- Acceptance: verification, invitation, and reset messages arrive in a real mailbox; secrets and raw tokens do not appear in production logs; failures are observable and retryable.

### P0.4 Update backend CI architecture contracts

- Backend: update OpenAPI/table/migration expectations to 66 paths, 90 operations, 27 SQLAlchemy application tables, and head `b7c9d2e4f601`; prefer intentional snapshots that clearly explain future diffs. Database-level checks should expect 28 physical tables when `alembic_version` is counted.
- Frontend: no feature change.
- Database: migration test remains isolated.
- Dependencies: CI PostgreSQL service.
- Estimate: 0.5 day.
- Acceptance: backend CI passes at current head and fails meaningfully when API/schema changes are unreviewed.

### P0.5 Establish minimum deployment safety

- Backend: add readiness/liveness checks, validated strong JWT secret policy, production URL/TLS validation, explicit trusted-proxy configuration, and structured logs.
- Frontend: environment-specific API/deep-link configuration and release smoke test.
- Database: automated encrypted backup plus documented restore procedure.
- Dependencies: target hosting choice, secret manager, monitoring destination, durable object storage.
- Estimate: 3–6 days for an initial production baseline.
- Acceptance: a staging deployment can be reproduced, monitored, backed up, restored, and smoke-tested without source edits.

## P1 — finish existing core value

### P1.1 Implement the farm-manager dashboard

- Backend: reuse effective-permission endpoint; no owner privilege inheritance.
- Frontend: add a permission-driven manager dashboard and tests; avoid hardcoding owner-only actions.
- Database: none.
- Dependencies: agreed manager UX.
- Estimate: 1–2 days.
- Acceptance: a manager no longer sees “Unsupported farm role,” can reach every allowed module, and cannot reach owner-only actions.

### P1.2 Complete health and veterinary frontend workflows

- Backend: stabilize current contracts and add pagination/filter gaps discovered during UI integration.
- Frontend: encounters, diagnosis, vaccination schedules/administration, treatments, medication, visits, reminders, corrections, and audit/history screens with role-aware actions.
- Database: likely none initially; indexes may be justified after query profiling.
- Dependencies: veterinary workflow validation and accessible mobile forms.
- Estimate: 7–12 days.
- Acceptance: owner/manager/veterinarian can complete authorized clinical journeys; workers can perform only intended reporting/viewing; farm isolation and all 403 cases have tests.

### P1.3 Complete milk frontend workflows

- Backend: stabilize session, bulk, lactation, quality, correction, and analytics contracts.
- Frontend: daily entry, bulk entry, lactations, quality, correction history, and owner/manager analytics.
- Database: profile query performance and add reviewed indexes only if evidence requires them.
- Dependencies: farm data-entry UX validation.
- Estimate: 6–10 days.
- Acceptance: authorized users can record and review production without API tooling; corrections remain auditable; analytics reconcile with raw sessions.

### P1.4 Finish cattle weight and media journeys

- Backend: confirm upload size/type policy, authorization, content disposition, and storage abstraction.
- Frontend: weight timeline/add form and media upload/gallery/download/delete.
- Database: none unless media metadata changes.
- Dependencies: durable object storage decision and upload limits.
- Estimate: 3–5 days.
- Acceptance: supported clients complete weight and media workflows; unauthorized access and cross-farm media access fail.

### P1.5 Complete account/profile controls

- Backend: profile update, authenticated password change, optional revoke-all-sessions, and audit events.
- Frontend: edit profile, change password, session feedback, and verification state.
- Database: possibly session/revocation or audit table depending on chosen design.
- Dependencies: account policy decisions.
- Estimate: 3–5 days.
- Acceptance: users can safely update allowed fields and password; prior sessions follow the documented invalidation policy.

### P1.6 Build real system-administration navigation

- Backend: define narrowly scoped platform endpoints for breed catalog and any approved operational tasks; keep farm and platform authority separate.
- Frontend: separate system-admin shell and working breed catalog management UI.
- Database: audit records recommended for platform mutations.
- Dependencies: explicit admin requirements.
- Estimate: 3–5 days.
- Acceptance: system admins can manage the approved global catalog without a farm membership; non-admins cannot access platform APIs.

### P1.7 Add farm settings and lifecycle

- Backend: update settings, archive policy, ownership-transfer workflow, and audit rules.
- Frontend: settings and confirmation flows.
- Database: settings/audit additions as required.
- Dependencies: business rules for transfer/archive/delete.
- Estimate: 3–5 days.
- Acceptance: lifecycle operations preserve history, require appropriate authority, and cannot orphan a farm.

## P2 — product expansion

### P2.1 Feed and inventory management

- Backend/database: feed items, batches, stock movements, rations, consumption, suppliers, constraints, and audited adjustments.
- Frontend: inventory, receiving, ration planning, consumption, low-stock views.
- Dependencies: units-of-measure policy and costing rules.
- Estimate: 8–12 days.
- Acceptance: stock reconciles from immutable movements; farm isolation and manager/worker permissions are tested.

### P2.2 Breeding and reproduction

- Backend/database: heat events, services/insemination, pregnancy checks, expected calving, births, lineage rules, reminders.
- Frontend: cattle timeline and breeding worklists.
- Dependencies: veterinarian/farm domain validation.
- Estimate: 8–12 days.
- Acceptance: reproductive lifecycle is traceable and invalid sequences are rejected.

### P2.3 Finance, salary, and farm resources

- Backend/database: chart of categories, income/expense ledger, payroll periods, staff compensation, equipment/resources, attachments, audit trail.
- Frontend: role-limited entry, review, approvals, summaries, exports.
- Dependencies: currency/tax/payroll scope and privacy rules.
- Estimate: 12–20 days, preferably split into finance, payroll, and resources increments.
- Acceptance: balances are reproducible from records; sensitive salary data has stricter permissions and audit coverage.

### P2.4 Reporting and exports

- Backend: cross-domain report queries, asynchronous exports, row limits, authorization, and audit.
- Frontend: owner/manager report builder, saved filters, exports, and KPI definitions.
- Database: reporting indexes/materialized views only after profiling.
- Dependencies: agreed metric dictionary.
- Estimate: 6–10 days.
- Acceptance: report totals reconcile with source records and exports never cross farm boundaries.

### P2.5 Notifications and preferences

- Backend/database: event types, per-user/farm preferences, delivery outbox, retries, deduplication, and status history.
- Frontend: notification center and channel/topic preferences.
- Dependencies: email provider; optional push provider.
- Estimate: 6–10 days.
- Acceptance: reminders produce deduplicated notifications according to user preferences and failures are observable.

### P2.6 Marketplace

- Backend/database: listings, inventory linkage, inquiries/orders, moderation, transaction states, and audit.
- Frontend: discovery, listing management, transaction workflow.
- Dependencies: legal/business scope, payments decision, moderation policy.
- Estimate: 12–20 days before payments; more with payment processing.
- Acceptance: explicit state machine, ownership checks, moderation, and no implicit financial settlement.

### P2.7 Scale and security hardening

- Backend: shared Redis-backed rate limits, durable jobs/outbox, object storage, malware scanning, security headers, dependency/secret scanning, and performance tests.
- Frontend: offline/error strategy and telemetry consent.
- Database: retention, archival, index review, and connection-pool/load validation.
- Dependencies: Redis, object storage, monitoring, security tooling.
- Estimate: 6–12 days across incremental changes.
- Acceptance: multi-instance behavior is consistent; uploads are durable; abuse controls and operational alerts work under load.

## P3 — AI readiness and models

### P3.1 Data governance and MLOps foundation

- Define consent, ownership, anonymization, retention, label provenance, train/validation/test separation, farm-level leakage controls, baselines, approval, monitoring, and rollback.
- Version datasets and features; do not train from mutable production tables without a reproducible snapshot.
- Estimate: 5–10 days for policy/schema/pipeline design, before collection and labeling.
- Acceptance: every training row/image is traceable to an approved source and split; metrics and deployment thresholds are documented.

### P3.2 Early milk-production-drop detection

- Best first AI candidate because structured milk history already exists.
- Begin with transparent statistical baselines and rule-based alerts before complex ML.
- Backend/frontend: feature pipeline, evaluated detector, explanation, alert review/feedback, and monitoring.
- Database: model version, prediction, explanation, review outcome.
- Estimate: 3–6 weeks after sufficient clean longitudinal data exists.
- Acceptance: prospectively validated sensitivity/false-alert targets, farm-level leakage prevention, and human review before action.

### P3.3 Milk-yield prediction

- Requires enough history plus parity, lactation stage, health, feed, season, and missingness features.
- Estimate: 4–8 weeks after data readiness.
- Acceptance: beats a simple historical baseline on held-out farms/time periods; uncertainty is shown; drift is monitored.

### P3.4 Skin-disease image assistance

- Requires veterinary-approved labels, image capture protocol, consent, class balance, and an abstention/urgent-referral policy.
- Estimate: multi-month data program plus 6–10 weeks engineering/evaluation once data exists.
- Acceptance: external veterinary evaluation, calibrated confidence, safe abstention, and prominent non-diagnostic framing.

### P3.5 Breed identification assistance

- Requires representative labeled images across breeds, ages, lighting, regions, and crossbreeds.
- Estimate: 4–8 weeks after dataset readiness.
- Acceptance: evaluated on independent farms, supports “unknown/mixed,” and never silently overwrites authoritative cattle records.

## Suggested release sequence

- Release A: P0.1–P0.5 — deployable authentication and operational safety.
- Release B: P1.1, P1.4, P1.5 — close obvious role/account/cattle gaps.
- Release C: P1.2 — operational veterinary module.
- Release D: P1.3 — operational milk module.
- Release E: remaining P1 and chosen P2 business modules.
- AI track starts only after P3.1 and adequate real data accumulation; it should not block core product delivery.

## Single best next task

**Execute the reviewed `icms_db` migration-readiness and upgrade task for revision `b7c9d2e4f601`.**

It is the first task because the checked-in auth code and protected database are currently incompatible. The task must include a restorable backup, preflight/version capture, migration review, approved maintenance window, upgrade, schema verification, and authentication smoke tests. No new feature is safe to release ahead of this gate.
