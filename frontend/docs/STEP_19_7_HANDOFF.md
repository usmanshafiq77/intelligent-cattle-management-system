# Step 19.7 Account and Email Verification Handoff

Step 19.7 adds a protected, read-only profile screen and the real email
verification/recovery workflows supported by the FastAPI backend.

## Supported backend contracts

- `GET /api/v1/auth/me` returns the authenticated `UserResponse`: `id`,
  `full_name`, `email`, `is_system_admin`, `status`, `is_email_verified`, and
  `created_at`.
- `POST /api/v1/auth/verify-email` accepts `{ "token": string }` and returns
  a message response. Tokens are one-time and expire according to backend
  policy.
- `POST /api/v1/auth/verification/resend` accepts `{ "email": string }` and
  returns a generic accepted response to avoid account enumeration.

The current backend has no profile-update, password-change, or password-reset
endpoint. The profile therefore has no fake edit or save control.

## Routes and account state

- `/profile` is protected by the existing session guard and renders only the
  verified AuthProvider user.
- `/auth/verify-email` is intentionally public for the supported manual
  one-time-token workflow; it reveals no protected profile data when opened
  without a session.
- `/session` links to profile and remains a temporary authenticated destination
  until the Step 19.8 navigation shell is introduced.

Profile displays name, email, account creation date, safe account ID, accurate
active/inactive status, and email-verification status. It does not infer farm
membership or a farm role. An unverified user can open the verification screen
from their profile.

## Verification and resend behavior

The verification token is held only in screen state, never logged or persisted.
Successful verification clears the input and refreshes `/auth/me` through the
existing AuthProvider so `is_email_verified` is current. Invalid, expired, or
used codes receive safe recovery guidance.

Resend normalizes the entered email and always uses an enumeration-safe success
message. It neither auto-retries nor reveals whether an account exists. A 429
with `Retry-After` activates a visible local cooldown.

Profile refresh and verification hydration use the AuthProvider operation
generation safeguards. A logout or newer session prevents stale user data from
being written back. A session expiry continues to remove protected content.

## Verification

Run from `frontend`:

```powershell
npm.cmd test
npx.cmd expo install --check
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

Tests cover profile rendering and statuses, refresh/logout races, protected
route policy, verification success/failure/duplicate submission, safe resend,
rate-limit cooldown, AuthProvider hydration, token storage, and prior UI
regressions. The tests use deterministic mocks only; no live user or database
record is created.

Local completion verification on 2026-10-16 passed: 13 structural checks and
102 UI tests (115 checks total), Expo dependency validation, and Expo Doctor
(21/21 checks). Web export and a local HTTP smoke check returned `200`; the
Android Hermes bundle completed successfully. Android emulator/device launch
was not performed because `adb` is not available in this environment.

## Remaining boundaries

Step 19.8 should replace the temporary session destination with farm-aware,
role-aware navigation. It must retain AuthProvider as the only session owner
and continue relying on backend RBAC for authorization. Actual Android/iOS
device testing remains necessary for SecureStore and visual verification.
