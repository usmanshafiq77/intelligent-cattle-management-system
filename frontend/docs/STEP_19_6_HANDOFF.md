# Step 19.6 Session Lifecycle Handoff

Step 19.6 provides secure credential storage, server-verified session state,
logout/expiry handling, and the first protected Expo Router destination. It
does not implement the final dashboard, farm context, or role-based tabs.

## Session lifecycle

`AuthProvider` is the single source of authentication state:

- `initializing`: stored credentials are being read or verified; navigation is
  held behind the existing startup gate.
- `unauthenticated`: no usable credential exists and only public auth routes
  are enabled.
- `authenticated`: `/api/v1/auth/me` returned a validated active user.
- `verification-unavailable`: storage or connectivity prevented a safe
  decision. Protected content remains unavailable and the user can retry or
  explicitly sign out.

On Android and iOS, `expo-secure-store` stores the access token under the
versioned `icms.access-token.v1` key. Web uses process memory only, so browser
refresh intentionally requires login again. Tokens are never placed in
AsyncStorage, browser storage, environment variables, URLs, or logs.

Startup reads the configured token provider exactly once and calls
`GET /api/v1/auth/me` when a token exists. A token alone never establishes an
authenticated state. The validated current-user contract contains `id`,
`full_name`, `email`, `is_system_admin`, `status`, `is_email_verified`, and
`created_at`.

## AuthProvider interface

`useAuth()` exposes:

- `status`, `user`, `sessionIssue`, `isAuthenticated`, and `isInitializing`
- `completeLogin(loginResponse)` to validate/store a login response and hydrate
  the current user
- `restoreSession()` / `retryVerification()`
- `logout()` / `clearSession()`

Operation generations prevent older login or restoration responses from
overwriting a newer login/logout. Credential deletion is deduplicated while in
flight. A late 401 includes the credential that actually failed and is ignored
if a newer token has replaced it.

## Failure and expiry policy

- `/auth/me` 401 or inactive-account 403 confirms the session is unusable and
  triggers credential removal.
- API-client 401 events clear only the matching current credential; repeated
  events for the same token are deduplicated.
- Network errors, timeouts, 429, and 503 do not delete a potentially valid
  stored token. The app enters `verification-unavailable` instead.
- Manual logout clears protected user state and securely removes the token.
  If secure deletion fails, ICMS blocks protected content and explicitly asks
  the user to retry; it does not claim logout succeeded.
- No refresh-token or automatic authentication retry behavior is fabricated.

## Protected navigation

Expo Router `Stack.Protected` enables welcome/login/signup only for an
unauthenticated session and enables `/session` only after server verification.
Initialization displays the startup gate, and verification failures display a
safe recovery screen rather than protected data. The development design-system
route retains its existing development-only wrapper.

`/session` displays only verified public profile fields and a working Logout
button. It is deliberately labelled as a temporary session confirmation, not a
dashboard. Backend authentication and RBAC remain authoritative.

## Verification

Run locally from `frontend`:

```powershell
npm.cmd test
npx.cmd expo install --check
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

The deterministic test suite covers native/web storage, restoration without a
token, valid/expired/invalid credentials, offline/timeout/503 behavior,
storage failures, current-user hydration, manual and event-driven logout,
overlapping operations, stale 401 events, route policy, themes, accessibility,
reduced motion, and all earlier frontend regressions. No real user account or
database is accessed.

Local completion verification passed 102 automated checks (13 structural and
89 Jest), Expo Doctor 21/21, the web production export and HTTP smoke check,
and the Android Hermes production bundle. ADB was not available, so actual
Android SecureStore/runtime behavior remains unverified on a device.

## Next integration boundaries

Step 19.7 may consume the verified `user` and authenticated route foundation;
it should not create another token store or AuthProvider. Step 19.8 can replace
the temporary `/session` destination with the reviewed farm-aware, role-based
navigation shell. Authorization must continue to rely on backend farm/RBAC
responses rather than claims inferred solely in the client.

Actual SecureStore behavior still requires Android/iOS device or emulator
validation. Jest verifies adapter behavior, serialization, and failure policy;
an Android production bundle is not equivalent to device runtime proof.
