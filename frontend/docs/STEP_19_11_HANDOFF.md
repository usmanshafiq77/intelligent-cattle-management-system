# Step 19.11 — Dashboard and Cattle Management Handoff

## Scope and architecture

Step 19.11 replaces the temporary dashboard and cattle placeholder with real,
farm-scoped UI. The implementation remains JavaScript-only and uses the
existing Expo Router, `AuthProvider`, `FarmProvider`, permission guards, API
client, and three-theme design system.

Routes:

- `/dashboard`: selected-farm header, role, real herd KPIs, status breakdown,
  permission-aware actions, module navigation, and theme controls.
- `/cattle`: cattle directory with complete-data search, sex/status filters,
  sorting, 20-item presentation pages, refresh, and profile navigation.
- `/cattle/register`: backend-connected registration for users with
  `cattle.create`.
- `/cattle/[id]`: backend-confirmed profile, refresh, and supported lifecycle
  transitions.
- `/cattle/[id]/edit`: backend-connected PATCH editing for users with
  `cattle.update`.

`useCattleCollection` retrieves server pages with `limit=200` and increasing
`offset` until the backend returns a short page. The safety ceiling is 50 pages
(10,000 loaded records). Dashboard values are labeled as totals only when that
process proves the dataset complete. If the ceiling is reached, the UI labels
the data as partial and states that client filters cover loaded records only.

Every cattle response is checked against the initiating farm. Requests are
aborted and/or ignored when their operation is no longer current. Create,
update, and lifecycle mutations are locked against duplicate presses. Ambiguous
network/timeout outcomes are never retried automatically.

## Actual FastAPI mapping

- `GET /api/v1/breeds`: authenticated active-breed catalog; supports `species`,
  `search`, `limit`, and `offset`.
- `POST /api/v1/farms/{farm_id}/cattle`: `cattle.create`; returns HTTP 201 and a
  `CattleResponse`.
- `GET /api/v1/farms/{farm_id}/cattle`: `cattle.view`; supports `search`,
  `species`, `sex`, `breed_id`, `status`, registration-date filters, `limit`,
  and `offset`. The response is an array and does not include a total count.
- `GET /api/v1/farms/{farm_id}/cattle/{cattle_id}`: `cattle.view`.
- `PATCH /api/v1/farms/{farm_id}/cattle/{cattle_id}`: `cattle.update`.
- `GET /api/v1/farms/{farm_id}/cattle/{cattle_id}/lifecycle`: `cattle.view`.
- `POST /api/v1/farms/{farm_id}/cattle/{cattle_id}/lifecycle`:
  `cattle.update`; valid transitions are Active to Missing, Sold, Transferred,
  Deceased, or Archived, and Missing to Active or Deceased.

There is no cattle DELETE endpoint. The frontend does not fabricate one.
Weight history and raw media endpoints exist, but Step 19.11 uses only the
`latest_weight` and `media_count` fields embedded in `CattleResponse`; dedicated
weight/media workflows remain outside this screen set. Health, milk, breeding,
feed, and finance summaries are not invented on the dashboard.

## Forms and data semantics

Registration sends only `CattleCreate` fields: normalized tag/name, species,
sex, category, optional breed and dates, acquisition data, color/marks/notes,
optional initial weight, and null parent IDs because parent selection is not yet
presented. Date, category/sex, money/currency, tag-length, and weight validation
mirror the backend rules.

Editing sends only fields accepted by `CattleUpdate`. Species and sex are shown
as immutable. Successful PATCH responses are validated and followed by a GET.
If that refresh fails, the UI reports that the save succeeded but current
values still require verification; it does not repeat the mutation.

Breed choices come from the authenticated global breed endpoint and are
filtered by the selected species. No photo control is displayed because a
cross-platform, reviewed binary-picker workflow is not part of the installed
dependency set.

## RBAC, tenancy, and failure handling

- List/profile/dashboard data requires `cattle.view`.
- Registration requires `cattle.create`.
- Editing and lifecycle status changes require `cattle.update`.
- Missing or unknown permissions deny access.
- Direct invalid IDs are rejected before an API request.
- Backend 401, 403, 404, 409, 422, 429, network/timeout, and 5xx outcomes are
  normalized without rendering sensitive server detail.
- Farm switch, logout/unmount, permission removal, and out-of-order completion
  cannot restore or navigate with stale farm data.
- Frontend guards are navigation assistance only; FastAPI remains authoritative.

## Dashboard data sources

The dashboard derives total/loaded, active, female, male, represented-breed,
and lifecycle-status values exclusively from verified cattle list responses.
It does not call health, milk, feed, finance, or report endpoints. An empty farm,
partial dataset, loading state, permission denial, backend error, retry, and
farm switching all have explicit UI states.

## Verification — 2026-10-17

- Focused Step 19.11 Jest suite: 43 passed, 0 failed.
- Full frontend Jest suite: 288 passed, 0 failed across 20 suites.
- Structural checks: 13 passed, 0 failed.
- Expo dependency compatibility: passed; installed versions are current for
  Expo SDK 57.
- Expo Doctor: 21/21 checks passed.
- Fresh web production export: passed at
  `dist/web-step19-11-final-20261017_093003`.
- Fresh exported web HTTP smoke: HTTP 200, valid HTML and Expo root present.
- Fresh Android/Hermes export: passed at
  `dist/android-step19-11-final-20261017_093021`; generated `.hbc` bundle.
- Android emulator/device runtime: not verified because no device was used.
- Live write integration: not performed. The running local backend was already
  connected to `icms_db`, so all cattle mutation behavior was verified with
  deterministic mocked API contracts rather than risk real records.
- No Alembic operation, database write, credential change, Git write, commit,
  push, or GitHub Actions trigger was performed.

## Step 19.12 handoff

Step 19.12 may perform manual GUI/device acceptance and Git finalization after
reviewing all accumulated local changes. A future cattle enhancement can add a
reviewed cross-platform media picker/upload experience and dedicated weight
history UI. Those should preserve the same farm-response validation and
mutation-race controls.
