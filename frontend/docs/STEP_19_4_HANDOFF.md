# Step 19.4 Entry Experience Handoff

Step 19.4 replaces the development showcase at `/` with the real ICMS entry
experience. It adds native splash coordination, original lightweight branding,
responsive welcome content, honest authentication placeholders, an unknown-route
fallback, and a production guard for developer-only UI.

## Application flow

```text
Native splash -> theme restoration -> Welcome
                                  |-> /auth/signup (Step 19.5 placeholder)
                                  |-> /auth/login  (Step 19.5 placeholder)
```

The placeholders collect no credentials, create no users, and establish no
session. Step 19.5 can replace their route components without changing the
welcome screen URLs.

## Native splash and initialization

`app.json` configures the Expo SDK 57 `expo-splash-screen` plugin with an
emerald background, contained ICMS mark, 200-pixel logical image width, and a
midnight dark-mode background. `app/_layout.jsx` prevents automatic dismissal
at module load. `StartupGate` dismisses the native splash as soon as theme
restoration finishes; it introduces no fixed delay. Initialization rejection
falls back to Emerald Luxury and still exposes the application.

Expo Go and web can validate JavaScript startup, but native resource changes
require a rebuilt development or release binary. A true Android cold-start
inspection therefore requires a native build installed on an emulator/device.

## Welcome architecture

- `src/features/onboarding/screens/WelcomeScreen.jsx` owns the responsive entry
  layout and Expo Router actions.
- `src/components/brand/BrandMark.jsx` provides the accessible in-app mark.
- `src/components/brand/FarmIntelligenceGraphic.jsx` is a lightweight,
  code-native farm illustration with no external artwork or licensing burden.
- `src/features/auth/screens/AuthComingSoonScreen.jsx` clearly identifies the
  upcoming login and signup work without resembling a working form.
- `src/features/navigation/screens/NotFoundScreen.jsx` handles unknown or
  unavailable routes.

The screen uses the existing three-theme system, safe-area container, reusable
buttons, responsive breakpoints, visible web focus states, and reduced-motion
aware `FadeInView` transitions. No continuous animation runs in the background.

## Branding assets

The editable source mark is `assets/branding/icms-mark.svg`. The app icon,
native splash image, Android adaptive layers, monochrome Android icon, and web
favicon are deterministic PNG derivatives. Regenerate them on Windows with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate-brand-assets.ps1
```

The mark is original project artwork: a simplified cattle face and leaf in the
existing emerald, teal, cream, and gold palette.

## Routes

- `/` — production welcome screen
- `/auth/signup` — nonfunctional Step 19.5 account-creation introduction
- `/auth/login` — nonfunctional Step 19.5 login introduction
- `/dev/design-system` — Step 19.2 showcase in development only
- unmatched paths — accessible not-found screen with a route home

The development showcase remains fully functional when `__DEV__` is true. A
direct production request renders the same not-found experience as unavailable
content; hiding a link is not relied on as protection.

## Development access

Start Expo and open the normal home route:

```powershell
cd D:\ICMS_Project\frontend
npm.cmd start
```

During a development build, visit `/dev/design-system` on web to inspect theme
selectors and the Step 19.2 component catalogue. It is intentionally
unavailable in production exports.

## Verification

```powershell
npm.cmd test
npm.cmd run check:dependencies
npm.cmd run doctor
npm.cmd run export:web
npm.cmd run bundle:android
```

The tests cover native splash configuration and failure handling, initial theme
restoration, all themes, welcome rendering, both navigation actions, back
behavior, auth-placeholder honesty, development/production showcase behavior,
reduced motion, accessibility labels, and prior design/API regressions.

## Step 19.5 handoff

Replace the two placeholder route bodies with real authentication screens and
use the existing Step 19.3 `authApi` and auth transport. Preserve `/auth/login`
and `/auth/signup`, do not persist tokens in AsyncStorage, and keep session
persistence for the explicitly scheduled secure-storage work.
