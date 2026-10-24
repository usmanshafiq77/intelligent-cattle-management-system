# ICMS Business Logic Review

Review date: 2026-10-24

## Verified workflows

- Signup -> verification -> login: verification tokens are stored as hashes, expire, are consumed once, and delivery failures do not leak tokens (`backend/app/api/v1/auth.py`, `services/email_verification.py`).
- Forgot password -> reset -> re-login: responses resist account enumeration; reset tokens are hashed/single-use and increment the user's token version so old access tokens fail (`services/password_reset.py`, `core/security.py`).
- Farm ownership and invitations: active membership is required; invitations are role constrained and acceptance is tested (`api/v1/invitations.py`, `tests/test_invitation_*`).
- Farm switching: API calls require the requested farm ID plus an active membership/permission; frontend active-farm state is centralized in `FarmProvider.jsx`.
- Cattle: normalized farm-scoped tags, parentage checks, lifecycle state handling, weights and validated media are implemented (`api/v1/cattle`, `services/cattle.py`).
- Health: workers can record observations but clinical actions are permission-separated; corrections preserve history (`api/v1/health`, `tests/test_health.py`).
- Milk: lactation/animal eligibility, duplicate session protection, effective corrected volume, analytics and sale availability are enforced (`services/milk.py`, `services/finance.py`).
- Feed: purchase and adjustment movements are immutable ledger events; consumption locks stock and prevents negative inventory; idempotency and concurrency have tests (`services/feed.py`, `tests/test_feed_concurrency.py`).
- Breeding: heat, service, pregnancy, loss, calving, offspring and pedigree rules are farm-scoped; veterinarian authority is tested (`services/breeding.py`).
- Finance: Decimal quantization, posted-entry immutability, audited adjustments, currency-consistent payments, outstanding balances and formula-safe spreadsheet cells are implemented (`services/finance.py`).
- Marketplace: listing transitions, farm/cattle eligibility, seller authority, private contact handling, reports/moderation, and atomic cattle-sale/Finance creation are implemented (`services/marketplace.py`).

## Cross-module integrity

| Workflow | Result | Evidence |
|---|---|---|
| Feed purchase -> stock -> Finance expense | VERIFIED | `post_feed_purchase`; duplicate request and concurrency tests. |
| Milk production -> available volume -> sale income | VERIFIED | `available_milk`; Finance API tests prevent overselling. |
| Breeding -> pregnancy -> calving -> calf | VERIFIED | Breeding integration and concurrency tests. |
| Marketplace sale -> cattle status -> one Finance transaction | VERIFIED | Marketplace atomic-sale and duplicate-confirmation tests. |
| Password reset -> old JWT invalid | VERIFIED | Authentication/password-reset tests. |
| Farm isolation across operational modules | VERIFIED | Permission dependency plus module isolation tests. |
| Owner invites worker/veterinarian | VERIFIED | Invitation management/acceptance tests. |
| Health and milk use from frontend | INCOMPLETE | No `frontend/app/health` or `frontend/app/milk` routes. |

## Remaining business gaps

- P1: add health/vaccination and milk frontend workflows so backend functionality is operational for users.
- P1: implement a general task-assignment and reminder inbox. Dashboard task cards do not constitute a complete workflow.
- P1: add unified farm insights that reconcile feed, health, breeding, milk and Finance metrics.
- P2: complete user/farm preference administration and the system-admin breed-catalog interface.
- P2: connect scheduled jobs for reminders, notification delivery and backup monitoring.
- P3: AI features require datasets, evaluation criteria, model governance and explicit non-veterinary disclaimers before product integration.

No critical data-corruption or cross-farm logic defect remained after the test pass. The receipt caching/content-sniffing issue was fixed and regression-tested.
