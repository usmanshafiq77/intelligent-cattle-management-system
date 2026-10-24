# Step 19.9 Farm Creation, Onboarding, Selection, and Details Handoff

Step 19.9 adds real farm-management frontend workflows using only reviewed
FastAPI contracts. It reuses the Step 19.8 FarmProvider and does not alter the
authentication, API-client, RBAC, or token-storage architecture.

## Reviewed backend contracts

- `POST /api/v1/farms` accepts `name` (required, trimmed, 2–150 characters),
  optional `location` (trimmed, maximum 255 characters), and optional
  `description` (trimmed, maximum 2,000 characters). It returns `FarmResponse`.
  The backend creates the authoritative active `FARM_OWNER` membership in the
  same transaction.
- `GET /api/v1/farms` returns only farms where the current user has an `ACTIVE`
  membership.
- `GET /api/v1/farms/{farm_id}` returns a farm only to an active member.
- Effective role and permissions remain available from
  `GET /api/v1/farms/{farm_id}/staff/permissions/me`.

There is no reviewed `PATCH`, `PUT`, or `DELETE` farm endpoint. Farm details
are therefore intentionally read-only; the UI contains no fake edit or delete
action.

## Routes and workflows

- `/farm/create` is authenticated and creates a real farm through
  `FarmProvider.createFarm()`.
- `/farm/select` presents the server-verified accessible farm list.
- `/farm/details` reloads the active farm through its detail endpoint and
  displays supported fields only.
- `/dashboard` presents Create Farm for an account with no accessible farm and
  Add Farm for an existing owner/member.

After a successful `POST`, FarmProvider fetches the active farm list again,
requires the created ID to be present in that server response, then retrieves
effective permissions before activating the new farm. The client does not set
an owner role locally. If creation succeeds but list/permission hydration is
unavailable, the UI reports the confirmed creation and asks the user to refresh
instead of retrying blindly.

## Safety and context behavior

Farm selection accepts only IDs already returned by `GET /farms`. Every switch
clears the previous farm, membership, and permission state before starting the
next verification request. Abort signals and operation generations ignore late
responses. Logout or session loss clears the entire farm context.

Timeouts, network errors, and malformed/ambiguous creation responses prompt a
farm-list refresh before another create attempt, avoiding duplicate farms.
401 session handling remains owned by the shared authenticated API transport;
403 is kept as an authorization failure rather than treated as automatic logout.
Client guards improve navigation safety, but FastAPI remains authoritative for
membership, ownership, and permissions.

## UI and accessibility

The creation, selection, and details screens reuse the existing three themes,
cards, inputs, feedback, responsive layout, reduced-motion behavior, and
44-point interactive controls. Required fields, local lengths, backend field
errors, loading state, duplicate-submit prevention, and safe retry messaging
are covered. The selection screen supports zero, one, and multiple active farms
without fabricating entries.

## Tests and validation

Run from `frontend`:

```powershell
npm.cmd test
npx.cmd expo install --check
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

The Step 19.9 tests use deterministic API fixtures, not a live database. They
cover form validation, normalized payloads, backend field errors, duplicate
submissions, ambiguous network outcomes, activation after creation, selection,
details, safe error behavior, and existing FarmProvider races. No isolated live
integration test is claimed unless separately run against `icms_test`.

Local completion verification on 2026-10-17 passed 13 structural checks and
147 Jest UI/contract tests (160 checks total), with no failures or skips. Expo
dependencies are compatible and Expo Doctor passed 21/21 checks. Web production
export, Android Hermes production bundle, and a local web HTTP smoke check
(`200`) passed. Android runtime launch is not verified because `adb` is not
available in this environment.

## Step 19.10 handoff

Staff Management should use `useActiveFarm()` and `useCan()` / `RequirePermission`
for presentation only, pass the verified active farm ID to staff services, and
continue relying on FastAPI for enforcement. It should add no parallel farm
state store and must not invent farm editing functionality without new backend
endpoints.
