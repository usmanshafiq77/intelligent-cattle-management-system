# ICMS Remaining Roadmap

Updated: 2026-10-24

## P0 - production activation blockers

1. Rehearse and approve the documented backup/restore and migration procedure, then migrate `icms_db/public` from `a8b3c4d5e6f7` through `f1a3b5c7d906` in a maintenance window.
2. Configure verified SMTP sender identity, SPF/DKIM/DMARC, HTTPS verification/reset/invitation URLs, and send one approved verification message.
3. Provision production HTTPS hosting, secret management, narrow CORS origins, persistent media/object storage, monitoring and alerting.
4. Resolve or formally risk-accept the eight transitive npm advisories through an Expo-supported upgrade; add Python vulnerability scanning in standard CPython CI.
5. Perform post-migration smoke tests, backup restore rehearsal and rollback decision checks without destructive production downgrades.

## P1 - required FYP completeness

1. Build Health/Veterinary/Vaccination frontend routes, forms, reminders and role-aware clinical workflows.
2. Build Milk Production frontend recording, correction, analytics and sale-availability screens.
3. Implement general task assignment, reminders and an application-wide notification inbox with scheduled delivery.
4. Add unified reports/insights across cattle, health, milk, feed, breeding and Finance.
5. Complete user/farm settings and the system-admin global breed-catalog interface.
6. Run scripted end-to-end browser/mobile smoke tests and a physical Android device acceptance pass.

## P2 - operational hardening

1. Replace process-local auth throttling with a shared Redis-backed limiter.
2. Add centralized structured logs, metrics, error reporting and audit-event review UI.
3. Add scheduled encrypted off-site backups, retention policy, restore drills and evidence reports.
4. Improve pagination/search consistency, accessibility audits and visual regression coverage.
5. Increase focused coverage on presently unexecuted service/error branches above the current 89% statement level.

## P3 - AI and enhancements

1. Define ethically sourced datasets, consent/privacy rules, target metrics and veterinary safety boundaries.
2. Develop and validate milk-yield prediction as decision support, not guaranteed output.
3. Develop skin-disease triage with explicit non-diagnostic labeling and clinician escalation.
4. Develop breed identification with confidence thresholds and unknown-class handling.
5. Version models, monitor drift and document reproducible training/evaluation before API/UI integration.

**Next recommended implementation task:** Health/Veterinary/Vaccination frontend integration. It unlocks an already mature backend and closes the largest non-AI demonstration gap without requiring protected database changes.
