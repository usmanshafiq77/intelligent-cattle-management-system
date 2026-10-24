# Signup Authentication Error Fix

Verified on 2026-10-17 on branch `feature/step19-react-native`.

## Root cause

The signup request and FastAPI registration contract were already aligned, but
the local frontend had no `frontend/.env` file and no `EXPO_PUBLIC_API_BASE_URL*`
variables in its process environment. `requireApiBaseUrl()` therefore threw an
`EnvironmentConfigurationError` with code `INVALID_API_CONFIGURATION` before
`fetch` was called. The signup screen treated that setup exception as an unknown
authentication failure and displayed the generic message:

`Authentication could not be completed. Please try again.`

The backend was also not listening when the incident was investigated. Starting
FastAPI alone could not resolve the failure because the already running Expo
bundle still had no API origin. The reported web animation fallback warning is
unrelated to authentication.

## Correct local configuration

The ignored local file `frontend/.env` now configures:

- Web and fallback API origin: `http://127.0.0.1:8000`
- Android Studio emulator API origin: `http://10.0.2.2:8000`
- Development-only safe API metadata logging

The shared client appends `/api/v1`; the configured origin must not include that
path. The resulting registration URL is exactly:

`http://127.0.0.1:8000/api/v1/auth/register`

The request is `POST` with JSON fields `full_name`, `email`, and `password`.
Password confirmation remains client-only and is never sent. `.env` remains
ignored and contains no credential, token, database URL, or JWT secret.

Expo embeds public variables when it starts, so it must be restarted after an
environment change. For local web development, use port 8081 because the current
FastAPI development CORS policy explicitly permits `http://localhost:8081` and
`http://127.0.0.1:8081`. Do not use a wildcard origin.

## Code changes

- Added the missing ignored local frontend API configuration.
- Mapped `INVALID_API_CONFIGURATION` to a specific safe setup message that asks
  the developer to check `frontend/.env` and restart Expo.
- Strengthened registration response validation for the complete reviewed
  `UserResponse`, including system-admin flag, account status, and creation time.
- Added exact signup method, payload, base URL, and single-prefix tests.
- Added signup tests for configuration failure, duplicate email, validation,
  unavailable network, timeout, rate limiting, service failure, successful email
  verification handoff, and credential-safe logging.

No password policy, email verification, authentication, rate limit, session, or
RBAC control was bypassed or weakened.

## Verification evidence

- Frontend focused authentication/API suites: 82 passed, 0 failed.
- Full frontend Jest suite: 245 passed, 0 failed, 0 skipped.
- Structural checks: 13 passed, 0 failed.
- Isolated backend registration/authentication/CORS tests: 12 passed against a
  UUID-named disposable schema in verified `icms_test`.
- Runtime health endpoint: HTTP 200 at the configured origin.
- Runtime database health endpoint: HTTP 200 using a read-only check.
- Runtime CORS preflight from `http://localhost:8081`: HTTP 200 with that exact
  allowed origin.
- Live OpenAPI: registration POST and documented 201 response present.
- Expo Doctor: 21/21 checks passed.
- Web production export, fresh HTTP smoke, and Android Hermes export: passed.

The isolated backend tests execute real registration, duplicate detection,
password hashing, email-verification issuance, login, session protection, rate
limits, and CORS through FastAPI TestClient. No registration request was sent to
`icms_db`. A browser-driven form submission was not performed, so the final
manual browser interaction remains a user-environment check rather than claimed
automated evidence.

## Safe local startup and manual verification

Open two PowerShell terminals.

Backend:

```powershell
cd D:\ICMS_Project\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend web, with a clean environment reload:

```powershell
cd D:\ICMS_Project\frontend
npm.cmd run check:api -- --db
npx.cmd expo start --web --port 8081 --clear
```

Then open the Expo web URL, create a disposable development account, and confirm
that the Account Created state requests email verification. Do not retry if the
browser reports a timeout or other ambiguous network result; check the server and
account state first. If Expo must use a different web origin, add only that exact
origin to the backend development CORS configuration and restart FastAPI.
