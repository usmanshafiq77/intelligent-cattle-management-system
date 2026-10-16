# ICMS Mobile

React Native mobile client for the Intelligent Cattle Management System. Step
19.2 adds the shared visual language and reusable interface primitives on top
of the Expo Router, JavaScript-only foundation. The showcase uses labelled
sample content only; it does not simulate authentication or database access.

## Requirements

- Node.js 22.13 or newer (Node 22 LTS is recommended for Expo SDK 57)
- npm
- Expo Go on a device, or Android Studio with an Android emulator
- The ICMS FastAPI backend when API integration is required

On Windows systems that block PowerShell script wrappers, use `npm.cmd` and
`npx.cmd` in place of `npm` and `npx`.

## Install and validate

```powershell
cd D:\ICMS_Project\frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run validate
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

Do not place credentials, JWTs, database URLs, or private keys in any
`EXPO_PUBLIC_*` variable. Expo embeds these values in the client application.

## API address configuration

`EXPO_PUBLIC_API_BASE_URL` is the origin of the FastAPI server without the
`/api/v1` suffix. The shared API client appends `/api/v1` consistently.

- Android Studio emulator: `http://10.0.2.2:8000`
- Genymotion emulator: `http://10.0.3.2:8000`
- iOS simulator: `http://127.0.0.1:8000`
- Physical device: `http://<development-computer-LAN-IP>:8000`

For a physical device, both devices must be on the same trusted network. Start
FastAPI on an interface reachable by that device and allow only the required
development port through the local firewall. Use HTTPS and an environment-
specific host outside local development.

Restart Expo after changing `.env` so the bundled public value is refreshed.

Step 19.3 provides separate platform overrides without duplicating URLs inside
service modules:

- `EXPO_PUBLIC_API_BASE_URL_WEB` for the browser on the development laptop.
- `EXPO_PUBLIC_API_BASE_URL_ANDROID` for the Android emulator or device.
- `EXPO_PUBLIC_API_BASE_URL` as the fallback, including physical-device LAN use.
- `EXPO_PUBLIC_APP_ENV=production` requires HTTPS.

Only public network configuration belongs in these variables. The validator
rejects embedded credentials, paths, queries, fragments, Android loopback
addresses, and insecure production URLs. See
[`docs/STEP_19_3_HANDOFF.md`](docs/STEP_19_3_HANDOFF.md) for the complete API
architecture, authentication transport, CORS policy, and integration commands.

With the backend running, perform a genuine read-only health check using:

```powershell
npm.cmd run check:api
npm.cmd run check:api -- --db
```

## Entry experience

The app opens on the production welcome experience. Native launch resources are
configured through Expo Splash Screen and remain visible only while the saved
theme preference is restored; no artificial startup delay is used.

- `Get Started` opens the clearly labeled Step 19.5 signup placeholder.
- `Log In` opens the clearly labeled Step 19.5 login placeholder.
- Unknown links show a dedicated not-found screen.
- `/dev/design-system` preserves the Step 19.2 showcase in development builds
  and renders unavailable content in production.

See [`docs/STEP_19_4_HANDOFF.md`](docs/STEP_19_4_HANDOFF.md) for splash behavior,
branding assets, navigation, tests, and the Step 19.5 handoff.

## Run

```powershell
npm.cmd start
npm.cmd run android
```

For a deterministic JavaScript bundle check without an emulator:

```powershell
npm.cmd run bundle:android
```

## Architecture

```text
app/                    Welcome, auth placeholder, dev-only, and fallback routes
assets/branding/        Editable ICMS brand source
src/api/                FastAPI client, auth transport, routes, and domain services
src/components/brand/   Original in-app mark and farm intelligence illustration
src/components/ui/      Reusable, accessible interface primitives
src/config/             Environment and runtime configuration
src/features/           Domain-owned UI, hooks, validation, and API functions
src/navigation/         Shared route names and navigation policy
src/services/           Cross-domain device and infrastructure services
src/state/              Cross-feature application/session state
src/theme/              Themes, tokens, variants, and motion preferences
tests/                  Architecture, theme-contract, and component tests
```

Domain boundaries are reserved for authentication, farms, permissions, cattle,
health, and milk. Future breeding, feed, finance, reports, and marketplace
features should follow the same feature-local structure.

The root screen is a development showcase for the design system. Real
authentication and domain workflows belong to later approved substeps.

## Design system

Three persisted themes are available: Emerald (default), Midnight, and Indigo.
`ThemeProvider` restores the selected theme from AsyncStorage, validates stored
values, and rolls back an optimistic change if persistence fails. Application
code should consume `useTheme()` rather than importing theme colors directly.

The shared primitives include buttons, inputs, cards, statistic cards, status
badges, skeletons, inline feedback, full feedback states, confirmation dialogs,
and reduced-motion-aware entrance animation. Their size and color variants come
from `src/theme`; feature screens should avoid duplicating those contracts.

- Interactive controls retain a minimum 44-point touch target.
- Inputs expose labels, hints, validation alerts, password visibility controls,
  and keyboard focus treatment.
- Buttons announce busy and disabled state to assistive technology.
- Status variants meet WCAG AA contrast in every supplied theme.
- Responsive containers cap wide layouts while remaining fluid on phones.
- Motion utilities respect the operating system reduce-motion preference.

Run the focused component and contract checks with:

```powershell
npm.cmd run test:ui
npm.cmd run test:structure
```

The web export is emitted to `dist/web` and the Android bundle check to
`dist/android`; both paths are ignored build artifacts.

## Dependency notes

Use `npm.cmd run doctor` and `npm.cmd run check:dependencies` before upgrading
Expo packages. Do not use `npm audit fix --force`: at the Step 19.2 checkpoint,
the production-tree audit reports 60 transitive findings (15 moderate, 45 high)
through Expo CLI, Router, Metro, React Native, and their build tooling. npm's
suggested forced resolutions cross supported Expo versions. Expo Doctor is the
compatibility authority for this SDK line, while these advisories remain a
tracked SDK-upgrade item; none are dismissed or force-fixed here.

Official references:

- <https://docs.expo.dev/versions/latest/>
- <https://docs.expo.dev/router/installation/>
- <https://docs.expo.dev/guides/environment-variables/>
