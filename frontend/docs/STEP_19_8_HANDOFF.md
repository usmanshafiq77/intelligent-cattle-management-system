# Step 19.8 Role-Based Navigation and Farm Context Handoff

Step 19.8 replaces the temporary authenticated landing destination with a
responsive application shell driven by server-verified identity, active farm
membership, and effective permissions. It does not implement farm CRUD, staff
management, or domain workflows reserved for later steps.

## Navigation architecture

- `/`, `/auth/login`, and `/auth/signup` remain public-only routes.
- `/auth/verify-email` remains reachable with or without a session because the
  backend supports manual one-time-token verification.
- `/dashboard`, `/profile`, `/session`, and `/farm/[module]` are inside the
  authenticated Expo Router guard. `/session` redirects to `/dashboard` for
  backward compatibility.
- `/farm/[module]` resolves only modules in the centralized reviewed catalog.
  Unknown modules fail closed, and known modules require an active farm plus
  their exact effective permission.
- `/dev/design-system` remains development guarded. Unknown routes return to
  the authenticated dashboard or public welcome page as appropriate.

The dashboard renders a sidebar at tablet/desktop widths and compact horizontal
navigation on phones. Both variants use accessible link semantics, selected
state, 44-point minimum targets, the existing reduced-motion-aware components,
and all three ICMS themes.

## Authentication and farm lifecycle

`AuthProvider` remains the only session owner. Once `auth/me` verifies a user,
`FarmProvider` requests `GET /api/v1/farms`. The backend query includes only
`ACTIVE` memberships, so an omitted farm is never treated as accessible.

- Zero farms: no farm is selected and no permission request is made.
- One farm: it is selected only from the freshly verified list, then its
  effective permissions are requested.
- Multiple farms: the user must explicitly choose one before farm-scoped
  content is rendered.
- Refresh: the active farm is retained only if it is still in the new verified
  list, and its permissions are always revalidated.
- Switch: old farm identity, membership, and permissions are removed before the
  next request starts.
- Logout/session loss: pending farm requests are cancelled and all farm state
  is cleared.

Operation generations and abort signals prevent late list or permission
responses from restoring stale cross-farm state. No active-farm ID is persisted
or trusted from storage.

## Backend RBAC mapping

Identity and global system-admin status come only from `GET /auth/me`.
Farm roles and permissions come only from
`GET /farms/{farm_id}/staff/permissions/me`, whose response identifies the
membership, predefined role, custom role IDs, and effective permission codes.

The frontend recognizes the backend roles `FARM_OWNER`, `FARM_MANAGER`,
`WORKER`, and `VETERINARIAN`. Unknown roles fail contract validation. Farm menus
are permission-based rather than inferred from role names:

- Farm Management: `farm.manage`
- Staff & Invitations: `staff.view`
- Cattle: `cattle.view`
- Health: `health.view`
- Milk Production: `milk.view`

Farm Owner, Worker, Veterinarian, and Farm Manager therefore see only modules
present in their backend-computed effective permission list. Missing and
unknown permissions default to denied. Module destinations currently show an
honest coming-soon status rather than simulated functionality.

`is_system_admin` is global, not a farm membership role. The current backend
supports system-admin mutation of the global breed catalog but has no general
platform dashboard or cross-farm impersonation endpoint. The shell therefore
shows a separate, non-interactive breed-catalog status entry and never grants a
system administrator farm context without an active membership.

## Guards and error behavior

`RequireFarm`, `RequirePermission`, `useCan`, and `useActiveFarm` centralize the
client authorization UX. They block rendering while auth, membership, or
permissions are unverified. A backend 403 remains an authorization failure and
does not clear the authentication token. Authenticated 401 handling stays in
the shared API transport and AuthProvider.

404/403 farm responses clear selected-farm state and provide no unauthorized
farm details. 429, 503, network, timeout, cancellation, and malformed-contract
responses use safe states with explicit retry where appropriate. Previously
rendered farm data is removed during every switch and revalidation.

Client-side navigation and guards are a usability layer only. FastAPI must
continue enforcing authentication, active membership, authoritative ownership,
and every permission on every request.

## Verification

Run from `frontend`:

```powershell
npm.cmd test
npx.cmd expo install --check
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

The deterministic tests use injected API clients and fixtures only. They cover
zero/one/multiple farms, explicit selection, role-aware menus, permission
guards, inactive/revoked access behavior, cross-farm isolation, rapid switches,
logout races, HTTP failure categories, mobile/desktop navigation, accessibility,
themes, session policy, and all earlier frontend regressions. No database or
live business record is accessed.

## Step 19.9 integration

Step 19.9 farm onboarding may call the existing farm creation service, then
invoke `refreshFarms()` and select the newly returned verified farm. New farm,
staff, cattle, health, or milk screens should remain under authenticated routes,
use `useActiveFarm()` for scope, use `useCan()` or `RequirePermission` for UX,
and pass the active farm ID to existing API service functions. They must never
use client visibility as a replacement for backend authorization.

Native Android/iOS device testing remains required for final responsive and
assistive-technology validation. Android bundle generation is not equivalent
to a device launch.

## Local completion results

Verification on 2026-10-17 passed 13 structural checks and 131 Jest UI/contract
tests (144 checks total), with no failures or skips. Expo dependencies are
compatible and Expo Doctor passed 21/21 checks. Web production export, Android
Hermes production bundle, and a local web HTTP smoke check (`200`) passed.
Android runtime launch is not verified because `adb` is unavailable in this
environment. All validation used deterministic frontend fixtures; no database,
backend record, credential, migration, or live authorization state was changed.
