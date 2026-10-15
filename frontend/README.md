# ICMS Mobile

React Native mobile client for the Intelligent Cattle Management System. Step
19.1 establishes an Expo Router, JavaScript-only foundation; it does not contain
mock authentication or fake database integration.

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
app/                    Expo Router route files and layouts
src/api/                Generic FastAPI HTTP client
src/components/         Reusable presentation components
src/config/             Environment and runtime configuration
src/features/           Domain-owned UI, hooks, validation, and API functions
src/navigation/         Shared route names and navigation policy
src/services/           Cross-domain device and infrastructure services
src/state/              Cross-feature application/session state
tests/                  Static architecture and configuration checks
```

Domain boundaries are reserved for authentication, farms, permissions, cattle,
health, and milk. Future breeding, feed, finance, reports, and marketplace
features should follow the same feature-local structure.

The root screen is intentionally a neutral Step 19.1 placeholder. Real
authentication and domain workflows belong to later approved substeps.

## Dependency notes

Use `npx.cmd expo-doctor` and `npm.cmd run check:dependencies` before upgrading
Expo packages. Do not use `npm audit fix --force`: at the Step 19.1 checkpoint,
npm proposes incompatible Expo downgrades/upgrades for transitive Metro, Router,
and Expo CLI advisories. Expo Doctor is the compatibility authority for this
SDK line, while the advisories remain an upgrade-planning item.

Official references:

- <https://docs.expo.dev/versions/latest/>
- <https://docs.expo.dev/router/installation/>
- <https://docs.expo.dev/guides/environment-variables/>
