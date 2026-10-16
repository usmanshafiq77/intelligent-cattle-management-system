# Step 19.3 API Integration Handoff

This layer connects future ICMS screens to the existing FastAPI `/api/v1`
contract. It does not add login, registration, farm, cattle, health, or milk
screens and does not persist authentication credentials.

## Configuration

Copy `.env.example` to `.env` and select only public network addresses:

- Web on the development laptop: `EXPO_PUBLIC_API_BASE_URL_WEB=http://localhost:8000`
- Android Studio emulator: `EXPO_PUBLIC_API_BASE_URL_ANDROID=http://10.0.2.2:8000`
- Physical Android device: set the Android or fallback URL to the laptop's LAN
  address, for example `http://192.168.1.50:8000`
- Production: set `EXPO_PUBLIC_APP_ENV=production` and use an HTTPS API origin

The physical device and laptop must be on a trusted network. Bind Uvicorn to an
interface reachable by the device and permit only the required development
port through the firewall. Never put database credentials, JWT secrets, access
tokens, private keys, or other secrets in an `EXPO_PUBLIC_*` variable because
Expo embeds public variables in the application bundle.

Platform-specific values override `EXPO_PUBLIC_API_BASE_URL`. The API prefix is
added centrally, so configured origins must not include `/api/v1`.

## Integration modules

- `src/config/environment.js`: platform selection and strict URL validation
- `src/api/client.js`: Fetch-based methods, timeouts, cancellation, query
  serialization, JSON, binary responses, and multipart preparation
- `src/api/errors.js`: normalized HTTP, validation, timeout, cancellation, and
  network errors
- `src/api/authTransport.js`: volatile token handling, a future secure-storage
  provider interface, and de-duplicated session-expiration events
- `src/api/routes.js`: encoded, centralized route construction
- `src/api/auth.js`: registration, login, current user, and email verification
- `src/api/farms.js`: accessible farms, creation, and detail
- `src/api/staff.js`: staff, predefined roles, and farm custom roles
- `src/api/invitations.js`: farm invitations, reissue/revoke, and authenticated acceptance
- `src/api/permissions.js`: effective permissions for the selected farm
- `src/api/cattle.js`: breeds, profiles, lifecycle, weights, and media
- `src/api/health.js`: encounters, diagnoses, vaccination, treatment,
  medication, veterinary visits, reminders, history, and corrections
- `src/api/milk.js`: lactations, sessions, quality, corrections, and analytics
- `src/api/connectivity.js`: read-only service and optional database health

Screens should import the appropriate domain service, not construct URLs or
authorization headers themselves.

## Verified backend contract

The reviewed backend OpenAPI document contains 63 paths and 87 operations with
SHA-256 `6199c4095b695675714e06923a73e68d82d28889be79ed6025dd853252842014`.
Frontend tests tie this checkpoint to the backend OpenAPI guard, so intentional
backend contract changes require an explicit frontend review.

Public operations are service health, database health, registration, login,
email verification, and verification resend. `/auth/me` and all farm, staff,
role, invitation, breed, cattle, health, and milk operations require a Bearer
access token. Invitation acceptance is also authenticated.

Login returns `{ access_token, token_type: "bearer" }`. Access tokens expire
after 30 minutes by default. The backend has no refresh-token, logout/revocation,
password-reset, or active-farm-selection endpoint. The client therefore never
fabricates refresh or automatic replay behavior. Farm selection starts from
`GET /farms`, and permissions come from
`GET /farms/{farm_id}/staff/permissions/me`.

Most collection endpoints use `limit` and `offset` plus domain filters. Cattle
media upload is raw image bytes with `filename` and `purpose` query parameters;
it is not a multipart backend endpoint. The shared client still supports
multipart bodies for future verified endpoints. Media content is downloaded as
a binary response.

## Authentication transport

After a successful login, call `setAccessToken`. The default token provider is
memory-only and is cleared when the process ends. Step 19.6 can register a
native secure-storage adapter with `configureAuthTokenProvider`; AsyncStorage is
deliberately not used for credentials.

Protected requests obtain the token centrally and attach `Authorization:
Bearer <token>`. An authenticated 401 emits one session-expiration event per
token. A 403 remains a permission/account-state error and does not expire the
session. There is no automatic token refresh and no automatic replay of writes.

Development logs contain only method, relative path, status, and duration.
Headers, tokens, query values, request bodies, and response bodies are excluded.

## Errors

`ApiError` distinguishes invalid requests (400), authentication (401),
authorization (403), unavailable/concealed resources (404), conflicts (409),
validation (422), rate limiting (429), server errors (500), unavailable service
(503), network failure, timeout, and cancellation. FastAPI validation arrays are
reduced to field/message maps without retaining rejected input values. Internal
server details and stack traces are never used as user-facing messages.

## Browser CORS and native networking

FastAPI allows only configured browser origins. Development defaults are
`http://localhost:8081` and `http://127.0.0.1:8081`; configure the JSON
`CORS_ALLOWED_ORIGINS` backend setting for other web origins. Wildcards and
credentialed origins are rejected, production origins must use HTTPS, cookies
are disabled, and only the required methods and headers are allowed.

CORS is enforced by browsers. Native React Native traffic is not subject to
browser CORS, but it still requires a reachable host address and normal backend
authentication.

## Verification commands

```powershell
cd D:\ICMS_Project\frontend
npm.cmd test
npm.cmd run check:dependencies
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android

# Requires a reachable backend and a configured .env
npm.cmd run check:api
npm.cmd run check:api -- --db
```

The first connectivity command checks only `/api/v1/health`; `--db` also calls
the read-only database health endpoint. These are genuine network diagnostics,
not mocked tests. Android runtime connectivity still requires Expo Go or a
development build installed in the emulator/device.
