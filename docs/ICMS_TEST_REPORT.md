# ICMS Test Report

Execution date: 2026-10-24

## Automated results

| Area | Command | Result |
|---|---|---|
| Backend full suite | `python -m pytest -q --cov=app` with an isolated `icms_test_<uuid>` schema | 261 passed, 0 failed, 0 skipped; 89% statement coverage (7,392 statements, 809 missed). |
| Frontend structure | `npm run test:structure` | 13 passed, 0 failed. |
| Frontend Jest | `npm run test:ui` | 25 suites, 321 tests passed, 0 failed. |
| Expo compatibility | `npm run check:dependencies` | Dependencies up to date. |
| Expo health | `npm run doctor` | 21/21 checks passed. |
| Web export | `npm run export:web` | Passed; production bundle emitted under ignored `frontend/dist/web`. |
| Android export | `npm run bundle:android` | Passed; bundle emitted under ignored `frontend/dist/android`. |
| Python integrity | `python -m pip check` | No broken requirements. |
| Static security | `python -m bandit -r app` | 2 low-confidence false positives; no medium/high finding. |
| Frontend dependency audit | `npm audit` | 5 high and 3 moderate transitive findings; breaking forced fix not applied. |

Backend coverage includes authentication, email delivery, password reset, RBAC, farm isolation, cattle, health, milk, feed, breeding, finance, marketplace, migrations, OpenAPI contracts, error paths and concurrency. Migration tests create disposable PostgreSQL schemas and drop only those generated schemas after execution.

## Database isolation

- Integration target: database `icms_test`, generated schema `icms_test_<uuid>`.
- Fixture verifies database identity and selected search path before creating tables.
- Protected `icms_db/public`, GUI schema `icms_test_gui_20261017103146_ca6015f2`, recovery databases and backups were not written.

## Warnings and gaps

- One Starlette deprecation warning reports the legacy `httpx` integration used by FastAPI TestClient.
- Python vulnerability enumeration is blocked locally by the nonstandard Python distribution lacking `venv`; CI follow-up is required.
- No physical-device, cross-browser visual, accessibility assistive-technology, real SMTP, cloud restore, load, or deployed-environment test was claimed.
- Health and milk have backend tests but lack frontend UI tests because those screens are not implemented.
