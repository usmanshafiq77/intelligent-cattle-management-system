# Step 19.5 Authentication Handoff

Step 19.5 replaces the login and signup placeholders with accessible,
responsive forms backed by the existing FastAPI authentication API.

## Implemented flow

- `/auth/login` validates and normalizes input, sends exactly `email` and
  `password` to `POST /api/v1/auth/login`, validates the token response, and
  places the access token in the existing volatile auth transport.
- `/auth/signup` sends exactly `full_name`, `email`, and `password` to
  `POST /api/v1/auth/register`. Password confirmation is client-only and is
  never transmitted.
- Successful registration shows the real pending email-verification state and
  can call the existing generic verification-resend endpoint.
- Both routes support keyboard-safe scrolling, autofill hints, password
  visibility controls, minimum touch targets, visible focus, loading states,
  duplicate-submit protection, cancellation on unmount, and all three themes.

## Backend contracts

Both endpoints accept JSON under the configured `/api/v1` prefix:

- `POST /auth/login`: `{ "email": string, "password": string }` returns
  `{ "access_token": string, "token_type": "bearer" }`.
- `POST /auth/register`: `{ "full_name": string, "email": string,
  "password": string }` returns the safe public user response with HTTP 201;
  it does not return a token.

Full names must contain 2–150 characters, email addresses at most 254, and
registration passwords 8–128 characters. Login accepts the existing password
up to 128 characters without imposing the registration minimum client-side.
The backend reports duplicate registration as 409, schema validation as 422,
invalid credentials as 401, and inactive login as 403.

The screen routes are `/auth/login` and `/auth/signup`. Welcome, cross-auth,
back, direct URL, and browser-refresh navigation all retain these stable route
names.

Backend validation remains authoritative. Client checks mirror the current
length and email rules only to provide immediate feedback. API errors are
translated into safe field or form messages for validation, invalid
credentials, inactive accounts, duplicate email, throttling, network timeout,
and server failures. Responses and credentials are never logged.

## Security and scope boundary

The access token is memory-only. It is not stored in AsyncStorage, browser
storage, logs, route parameters, or public Expo environment variables. Login
success deliberately does not simulate a dashboard: secure persistence,
session restoration, current-user loading, logout, and protected-route policy
belong to Step 19.6.

The backend has no password-reset endpoint, so this UI does not present a fake
reset workflow. Registration does not create farms, accept invitations, or
automatically log the user in.

## Verification

Run from `frontend`:

```powershell
npm.cmd test
npm.cmd run check:dependencies
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

The focused PostgreSQL integration check must set `TEST_DATABASE_URL` to the
isolated `icms_test` database. The backend test harness independently verifies
that database name, creates a uniquely named disposable schema, and refuses
`icms_db` before authentication tests execute.

Set the public API origin in `frontend/.env` as described in the README (for
example, an Android emulator normally uses `http://10.0.2.2:8000`). Never put
database credentials or authentication secrets in an `EXPO_PUBLIC_*` value.

## Step 19.6 handoff

Build the authenticated session lifecycle around the existing auth transport:
select a reviewed secure-storage strategy, restore and validate a session with
`/auth/me`, handle expiry, implement logout, and introduce protected navigation.
Do not infer refresh-token support because the backend currently exposes none.
