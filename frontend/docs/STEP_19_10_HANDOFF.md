# Step 19.10 — Staff, Invitations, and RBAC Frontend Handoff

Status: locally complete on 2026-10-17. This checkpoint did not access either
PostgreSQL database, did not run migrations, and did not perform any Git write.

## Architecture and authorization

The module reuses the existing `AuthProvider`, `FarmProvider`, Expo Router guards,
API client, design system, and all three application themes. Staff data is loaded
only when FarmProvider has a verified active farm and the effective permission set
contains `staff.view`. Unknown, missing, stale, or removed permissions deny access.

Owner controls require both the verified `FARM_OWNER` membership and, when auth
context is present, a match between the authenticated user ID and the farm's
authoritative `owner_id`. The same check protects direct navigation to the invite
route. These UI checks reduce accidental exposure; FastAPI remains the authority.

Regular member controls are never rendered for a `FARM_OWNER` row or for a row
whose `user_id` is the farm's `owner_id`. `FARM_OWNER` and `SYSTEM_ADMIN` are not
offered as assignable roles. The backend endpoints are owner-only and separately
reject changes to the authoritative owner, so a self-role change or
self-deactivation is not a supported operation. PostgreSQL has no `REVOKED`
membership status in the reviewed contract; membership status is changed only
between `ACTIVE` and `INACTIVE`.

## Reviewed FastAPI contract mapping

- `GET /farms/{farm_id}/staff` — `staff.view`; list verified members.
- `PATCH /farms/{farm_id}/staff/{membership_id}/role` — owner-only; exact body
  `{ role }`, limited to `FARM_MANAGER`, `WORKER`, or `VETERINARIAN`.
- `PATCH /farms/{farm_id}/staff/{membership_id}/status` — owner-only; exact body
  `{ status }`, limited to `ACTIVE` or `INACTIVE`.
- `GET /farms/{farm_id}/invitations` — owner-only; list invitations.
- `POST /farms/{farm_id}/invitations` — owner-only; exact body `{ email, role }`.
- `POST /farms/{farm_id}/invitations/{invitation_id}/revoke` — owner-only and
  pending invitations only.
- `POST /farms/{farm_id}/invitations/{invitation_id}/reissue` — owner-only;
  accepted and rejected invitations are ineligible.
- `POST /invitations/accept` — authenticated; exact body `{ token }`. The backend
  validates identity, verified email, invitation state, expiry, and membership.

Mutation responses and list responses are contract-validated. Invitation
responses must carry the initiating farm ID. After a successful mutation the UI
reloads server-authoritative staff/invitation data and refreshes FarmProvider.
Failure to refresh leaves a recoverable error state instead of claiming success.

## Concurrency and secret handling

Every staff/invitation request is bound to the initiating farm, authenticated
session, permission generation, and component lifetime. A farm switch, logout,
session expiration, permission change, or unmount aborts the request and
invalidates its generation. A late Farm A response therefore cannot update Farm B,
restore stale permissions, display stale feedback, or trigger a context refresh.
Only one confirmation mutation can be in flight; the synchronous ref guard also
blocks two presses before React has rerendered the loading state.

Invitation codes remain transient screen state. Acceptance clears the code after
success. Reissue responses are validated and discarded before the authoritative
list reload; a development-only `invitation_token` is never rendered, logged, put
in a URL, or persisted by this feature. Network and timeout outcomes are described
as ambiguous and instruct the user to refresh before retrying.

## Automated evidence

The final focused file contains 90 passing tests. It covers invitation creation
and acceptance, dedicated reissue success/failure/security behavior, revoke,
all three predefined role targets, activate/deactivate, cancellation, owner-row
protection, unsupported role denial, and direct-route authorization.

The executable mutation error matrix covers revoke, reissue, role update,
activate, and deactivate against each of: 401, 403, 404, 409, 422, 429, 503,
network failure, and timeout. That is 45 passing interaction cases. Each asserts
normalized feedback, one request only, no leaked server detail, no false refresh,
and no false success.

Deterministic deferred-promise tests cover all five mutations during farm switch,
all five during logout/session loss, all five duplicate submissions, out-of-order
farm list responses, permission removal, component unmount, mutation success with
refresh failure, and invalid mutation responses. Expired invitations cannot be
revoked; accepted/rejected invitations cannot be reissued. The actual API service
tests additionally verify the HTTP methods, paths, bodies, and abort options.

Final automated results from this working tree:

- Focused Step 19.10: 90 passed, 0 failed.
- Mutation error matrix: 45 passed, 0 failed.
- Deterministic race/lifecycle cases: 18 passed, 0 failed.
- Full Jest: 238 passed across 19 suites, 0 failed, 0 skipped.
- Structural checks: 13 passed, 0 failed.
- New Jest cases added during final closure: 79.

## Production verification

- `expo install --check`: dependencies are up to date.
- Expo Doctor: 21/21 checks passed.
- Fresh web production export: passed.
- Fresh local HTTP request against that export: HTTP 200 (`text/html`).
- Fresh Android Hermes production bundle: passed.
- Android/iOS runtime: not verified because ADB/emulator/device tooling was not
  available in this environment.
- Live backend integration: not performed. Deterministic mocks and contract tests
  were used, so neither `icms_db` nor `icms_test` was accessed.

## Deferred scope and next step

Custom-role assignment/removal is explicitly deferred to a dedicated advanced
RBAC milestone. Although the backend exposes these operations, this step does not
accept raw custom-role IDs without a reviewed role-definition and privilege-review
workflow.

No critical local Step 19.10 issue remains. Step 19.11 may proceed after the normal
project checkpoint, reusing the verified active-farm and effective-permission
context. This handoff does not start Step 19.11.
