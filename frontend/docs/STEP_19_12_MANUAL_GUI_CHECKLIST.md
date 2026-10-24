# Step 19.12 Manual GUI Acceptance Checklist

Use this checklist only with a backend whose database has been independently verified
as `icms_test` and whose test harness selects a new uniquely named disposable schema.
Never point these write workflows at `icms_db`. Use synthetic `example.com` accounts,
the test memory email transport, and no real personal data.

## Safe setup

- [ ] Confirm the Git branch is `feature/step19-react-native` with `git status --short --branch`.
- [ ] Confirm the backend process is distinct from any process connected to `icms_db`.
- [ ] Confirm `SELECT current_database()` is exactly `icms_test`.
- [ ] Confirm `SELECT current_schema()` is the current run's new `icms_test_<uuid>` schema.
- [ ] Confirm memory email delivery and test-only rate-limit settings are intentional.
- [ ] Configure web to the isolated backend origin; use `10.0.2.2` for an Android emulator.
- [ ] Start the frontend and record desktop, tablet, and mobile viewport sizes.
- [ ] Open browser developer tools and clear the console/network log.

## Owner account, verification, and session

- [ ] Welcome → Get Started opens Signup; Log In opens Login; browser Back remains usable.
- [ ] Submit blank/invalid name, email, password, and mismatched confirmation. Expected:
  inline accessible errors and no request.
- [ ] Register a unique `owner-<run>@example.com`. Expected: HTTP 201 and verification UI;
  password/token never appears in console output.
- [ ] Attempt duplicate registration. Expected: normalized conflict feedback, no data leak.
- [ ] Exercise the configured registration rate limit. Expected: 429 feedback and no retry loop.
- [ ] Enter an invalid and an expired 32+ character verification token. Expected: safe rejection.
- [ ] Resend verification. Expected: generic response that does not disclose account existence.
- [ ] Read the current token only from the isolated memory transport and verify once.
  Expected: success; replay is rejected.
- [ ] Login with incorrect then correct credentials. Expected: safe invalid-credential feedback,
  followed by `/auth/me` hydration and dashboard navigation.
- [ ] Refresh web while authenticated. Expected: web token is not persisted and login is required.
- [ ] On Android, relaunch. Expected: SecureStore restores and `/auth/me` revalidates the session.
- [ ] Disconnect the backend and retry. Expected: honest unavailable state, no fake success.
- [ ] Logout. Expected: token and farm state clear; direct protected URLs redirect safely.

## Farm creation, selection, and isolation

- [ ] Login as a verified zero-farm owner. Expected: honest no-farm state and Create Farm action.
- [ ] Validate empty/oversized fields, then create Farm A. Expected: owner membership from the
  backend, refreshed list, verified owner permissions, and dashboard selection.
- [ ] Create Farm B. Expected: both farms listed and explicit switching available.
- [ ] Switch A → B → A while requests are pending. Expected: no stale name, role, permission,
  staff, dashboard, or cattle state crosses farms.
- [ ] Try an unknown farm ID and a revoked/inactive membership. Expected: access-denied/not-found
  behavior and no locally fabricated privileges.
- [ ] Logout during a farm request. Expected: late responses do not restore farm context.

## Staff, invitations, and predefined RBAC

- [ ] As owner, open Staff and verify authoritative members only.
- [ ] Invite unique Worker, Veterinarian, and FARM_MANAGER test accounts. Expected: only supported
  roles are offered; success clears the email; validation/server errors are assertive alerts.
- [ ] Repeat a pending invitation. Expected: 409 conflict feedback without duplicate membership.
- [ ] Reissue one eligible invitation. Expected: original becomes unusable and only the new token works.
- [ ] Revoke a pending invitation after confirmation. Expected: acceptance is denied.
- [ ] Register and verify the intended invitee; accept its memory-transport token. Expected: correct
  active membership. Test wrong email, expired, revoked, and replayed tokens; all must fail safely.
- [ ] Change Worker ↔ FARM_MANAGER ↔ Veterinarian. Expected: navigation/actions follow refreshed
  backend effective permissions.
- [ ] Deactivate and reactivate a non-owner. Expected: deactivated access is denied immediately.
- [ ] Verify owner role/status controls never appear and backend owner safeguards still reject direct calls.
- [ ] Verify Worker/Veterinarian cannot access owner-only invitation controls by direct URL.
- [ ] Do not mark custom-role editing complete; it remains deferred.

## Dashboard and cattle

- [ ] Verify dashboard farm name and predefined role match the active server membership.
- [ ] On an empty farm, verify zero-cattle state and permitted registration action.
- [ ] Register cattle as owner/FARM_MANAGER using valid dates/category/sex/currency fields.
  Expected: backend-confirmed profile, dashboard refresh, and no duplicate submission.
- [ ] Attempt duplicate normalized tag. Expected: conflict feedback and one record only.
- [ ] As Worker without `cattle.create`, test button visibility and direct registration URL/API.
  Expected: denial; client UI never grants authority.
- [ ] Search by tag/name; filter sex/status; sort recent/tag/name; use pagination and refresh.
- [ ] Open profile and edit supported fields. Expected: PATCH response followed by confirmed GET.
- [ ] Exercise supported lifecycle transitions with confirmation; invalid transitions remain denied.
- [ ] Request another farm's cattle ID and an unknown ID. Expected: indistinguishable 404 behavior.
- [ ] Switch farms/logout during list/profile/mutation requests. Expected: stale responses are ignored.
- [ ] With more than the 10,000-record safety ceiling, verify dashboard says “Loaded,” not “Total.”

## Themes, responsive layout, and accessibility

- [ ] Test Emerald, Midnight, and Indigo on welcome, auth, dashboard, staff, and cattle screens.
- [ ] Reload after each theme change. Expected: theme persists, but web JWT does not.
- [ ] Test approximately 360 px mobile, 768 px tablet, and 1280+ px desktop widths.
- [ ] Verify no horizontal clipping, hidden submit controls, overlapping navigation, or unreadable text.
- [ ] Navigate all forms/buttons by keyboard on web; confirm visible focus and logical order.
- [ ] Confirm inputs have programmatic labels, errors are announced, and busy/disabled states are exposed.
- [ ] Test 200% browser zoom and device text scaling; content must remain operable and scrollable.
- [ ] Enable reduced motion. Expected: content remains visible without required animation.
- [ ] Run a screen reader on Android/web for headings, navigation, forms, alerts, status, and dialogs.
- [ ] Verify all touch targets are comfortable and at least 44 points where specified.
- [ ] Confirm the browser console has no severe errors and network logs contain no passwords or tokens.

## Completion evidence

- [ ] Record the tested frontend/backend URLs without recording credentials.
- [ ] Record browser/device/OS versions and viewport sizes.
- [ ] Save screenshots only with synthetic records and no visible tokens.
- [ ] Confirm the disposable schema belongs to this run before cleanup.
- [ ] Clean up only the current run's disposable schema through the harness; never delete older schemas.
- [ ] Record failures separately; do not convert pending runtime checks into passes.
