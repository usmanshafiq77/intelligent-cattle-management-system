import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function readJson(relativePath) {
  return JSON.parse(await readFile(path.join(projectRoot, relativePath), 'utf8'));
}

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    if (['node_modules', '.expo', 'dist', '.npm-cache'].includes(entry.name)) continue;
    const entryPath = path.join(directory, entry.name);
    files.push(...(entry.isDirectory() ? await walk(entryPath) : [entryPath]));
  }

  return files;
}

test('Expo Router is the application entry and plugin', async () => {
  const packageJson = await readJson('package.json');
  const appJson = await readJson('app.json');

  assert.equal(packageJson.main, 'expo-router/entry');
  assert.equal(packageJson.dependencies['expo-router'], '~57.0.29');
  assert.ok(appJson.expo.plugins.includes('expo-router'));
  assert.equal(appJson.expo.experiments?.typedRoutes, undefined);
});

test('project source stays JavaScript-only', async () => {
  const files = await walk(projectRoot);
  const typeScriptSources = files.filter((file) => /\.(ts|tsx)$/.test(file));

  assert.deepEqual(typeScriptSources, []);
});

test('required architecture and routes exist', async () => {
  const requiredPaths = [
    'app/_layout.jsx',
    'app/index.jsx',
    'app/+not-found.jsx',
    'app/auth/login.jsx',
    'app/auth/signup.jsx',
    'app/auth/verify-email.jsx',
    'app/auth/forgot-password.jsx',
    'app/reset-password.jsx',
    'app/session.jsx',
    'app/dashboard.jsx',
    'app/cattle/index.jsx',
    'app/cattle/register.jsx',
    'app/cattle/[id]/index.jsx',
    'app/cattle/[id]/edit.jsx',
    'app/feed/index.jsx',
    'app/feed/inventory.jsx',
    'app/feed/schedules.jsx',
    'app/feed/records.jsx',
    'app/feed/purchases.jsx',
    'app/feed/alerts.jsx',
    'app/feed/nutrition.jsx',
    'app/feed/reports.jsx',
    'app/breeding/index.jsx',
    'app/breeding/heat.jsx',
    'app/breeding/events.jsx',
    'app/breeding/pregnancy.jsx',
    'app/breeding/calving.jsx',
    'app/breeding/offspring.jsx',
    'app/breeding/pedigree.jsx',
    'app/breeding/calendar.jsx',
    'app/breeding/reports.jsx',
    'app/breeding/settings.jsx',
    'app/farm/[module].jsx',
    'app/farm/create.jsx',
    'app/farm/select.jsx',
    'app/farm/details.jsx',
    'app/profile.jsx',
    'app/dev/design-system.jsx',
    'assets/branding/icms-mark.svg',
    'src/components/brand/BrandMark.jsx',
    'src/components/brand/FarmIntelligenceGraphic.jsx',
    'src/features/onboarding/screens/WelcomeScreen.jsx',
    'src/features/auth/screens/LoginScreen.jsx',
    'src/features/auth/screens/SignupScreen.jsx',
    'src/features/auth/screens/SessionScreen.jsx',
    'src/features/auth/screens/SessionUnavailableScreen.jsx',
    'src/features/auth/screens/ProfileScreen.jsx',
    'src/features/auth/screens/VerificationScreen.jsx',
    'src/features/auth/screens/ForgotPasswordScreen.jsx',
    'src/features/auth/screens/ResetPasswordScreen.jsx',
    'src/features/auth/verificationErrors.js',
    'src/features/farms/farmContracts.js',
    'src/features/farms/farmValidation.js',
    'src/features/farms/farmErrors.js',
    'src/features/farms/context/FarmProvider.jsx',
    'src/features/farms/components/FarmSelector.jsx',
    'src/features/farms/screens/FarmCreateScreen.jsx',
    'src/features/farms/screens/FarmSelectionScreen.jsx',
    'src/features/farms/screens/FarmDetailsScreen.jsx',
    'src/features/permissions/permissionCatalog.js',
    'src/features/permissions/navigationConfig.js',
    'src/features/permissions/guards.jsx',
    'src/features/navigation/components/RoleNavigation.jsx',
    'src/features/navigation/screens/DashboardScreen.jsx',
    'src/features/navigation/screens/FarmModuleScreen.jsx',
    'src/features/cattle/cattleContracts.js',
    'src/features/cattle/cattleErrors.js',
    'src/features/cattle/cattleOptions.js',
    'src/features/cattle/hooks/useCattleCollection.js',
    'src/features/cattle/components/CattleForm.jsx',
    'src/features/cattle/components/CattlePage.jsx',
    'src/features/cattle/screens/CattleCreateScreen.jsx',
    'src/features/cattle/screens/CattleListScreen.jsx',
    'src/features/cattle/screens/CattleDetailScreen.jsx',
    'src/features/cattle/screens/CattleEditScreen.jsx',
    'src/features/auth/context/AuthProvider.jsx',
    'src/features/auth/storage/secureTokenStore.js',
    'src/features/auth/components/AuthLayout.jsx',
    'src/features/auth/validation/authValidation.js',
    'src/navigation/DevelopmentOnlyRoute.jsx',
    'src/navigation/StartupGate.jsx',
    'src/api/client.js',
    'src/api/authTransport.js',
    'src/api/errors.js',
    'src/api/routes.js',
    'src/api/auth.js',
    'src/api/farms.js',
    'src/api/staff.js',
    'src/api/invitations.js',
    'src/api/permissions.js',
    'src/api/cattle.js',
    'src/api/health.js',
    'src/api/milk.js',
    'src/api/feed.js',
    'src/api/breeding.js',
    'src/features/breeding/breedingErrors.js',
    'src/features/breeding/screens/BreedingScreens.jsx',
    'src/features/feed/feedErrors.js',
    'src/features/feed/screens/FeedScreens.jsx',
    'src/config/environment.js',
    'src/components/ui/Screen.jsx',
    'src/features/home/screens/WelcomeScreen.jsx',
    'src/navigation/routes.js',
    'src/navigation/sessionPolicy.js',
  ];

  for (const relativePath of requiredPaths) {
    const contents = await readFile(path.join(projectRoot, relativePath), 'utf8');
    assert.ok(contents.length > 0, `${relativePath} must not be empty`);
  }

  for (const feature of ['auth', 'farms', 'permissions', 'cattle', 'health', 'milk', 'feed', 'breeding']) {
    const entries = await readdir(path.join(projectRoot, 'src', 'features', feature));
    assert.ok(entries.includes('.gitkeep'), `${feature} feature boundary must exist`);
  }
});

test('native splash uses the supported Expo plugin and generated PNG assets', async () => {
  const appConfig = JSON.parse(await readFile(path.join(projectRoot, 'app.json'), 'utf8'));
  const splashPlugin = appConfig.expo.plugins.find(
    (plugin) => Array.isArray(plugin) && plugin[0] === 'expo-splash-screen',
  );

  assert.ok(splashPlugin, 'expo-splash-screen plugin configuration is required');
  assert.equal(splashPlugin[1].resizeMode, 'contain');
  assert.ok(splashPlugin[1].imageWidth >= 100 && splashPlugin[1].imageWidth <= 288);
  assert.match(splashPlugin[1].backgroundColor, /^#[0-9A-F]{6}$/i);

  for (const asset of ['icon.png', 'splash-icon.png', 'android-icon-foreground.png', 'android-icon-background.png', 'android-icon-monochrome.png']) {
    const file = await readFile(path.join(projectRoot, 'assets', asset));
    assert.deepEqual([...file.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.ok(file.length > 1000, `${asset} should contain generated artwork`);
  }
});

test('default route is user-facing and the design showcase is development guarded', async () => {
  const indexRoute = await readFile(path.join(projectRoot, 'app', 'index.jsx'), 'utf8');
  const devRoute = await readFile(path.join(projectRoot, 'app', 'dev', 'design-system.jsx'), 'utf8');

  assert.match(indexRoute, /features\/onboarding\/screens\/WelcomeScreen/);
  assert.match(devRoute, /DevelopmentOnlyRoute/);
  assert.doesNotMatch(indexRoute, /features\/home\/screens\/WelcomeScreen/);
});

test('environment example contains a public URL and no credentials', async () => {
  const example = await readFile(path.join(projectRoot, '.env.example'), 'utf8');

  assert.match(example, /^EXPO_PUBLIC_API_BASE_URL=/m);
  assert.match(example, /^EXPO_PUBLIC_API_BASE_URL_WEB=/m);
  assert.match(example, /^EXPO_PUBLIC_API_BASE_URL_ANDROID=/m);
  assert.doesNotMatch(example, /(password|secret|token|api_key)\s*=/i);
});

test('authentication transport never persists tokens in AsyncStorage', async () => {
  const apiDirectory = path.join(projectRoot, 'src', 'api');
  const apiFiles = (await readdir(apiDirectory)).filter((file) => file.endsWith('.js'));
  const sources = await Promise.all(
    apiFiles.map((file) => readFile(path.join(apiDirectory, file), 'utf8')),
  );

  assert.ok(sources.every((source) => !source.includes('@react-native-async-storage')));
});

test('session storage uses SecureStore natively and no persistent web storage', async () => {
  const packageJson = await readJson('package.json');
  const appJson = await readJson('app.json');
  const storage = await readFile(path.join(projectRoot, 'src', 'features', 'auth', 'storage', 'secureTokenStore.js'), 'utf8');

  assert.equal(packageJson.dependencies['expo-secure-store'], '~57.0.4');
  assert.ok(appJson.expo.plugins.includes('expo-secure-store'));
  assert.match(storage, /SecureStore/);
  assert.doesNotMatch(storage, /AsyncStorage|localStorage|sessionStorage/);
});

test('root navigation protects the role-aware dashboard and farm modules', async () => {
  const layout = await readFile(path.join(projectRoot, 'app', '_layout.jsx'), 'utf8');
  const sessionRoute = await readFile(path.join(projectRoot, 'app', 'session.jsx'), 'utf8');
  const dashboardRoute = await readFile(path.join(projectRoot, 'app', 'dashboard.jsx'), 'utf8');
  const farmRoute = await readFile(path.join(projectRoot, 'app', 'farm', '[module].jsx'), 'utf8');
  const createFarmRoute = await readFile(path.join(projectRoot, 'app', 'farm', 'create.jsx'), 'utf8');

  assert.match(layout, /Stack\.Protected/);
  assert.match(layout, /canAccessProtectedRoutes/);
  assert.match(layout, /verification-unavailable/);
  assert.match(layout, /FarmProvider/);
  assert.match(layout, /name="dashboard"/);
  assert.match(layout, /name="farm\/\[module\]"/);
  assert.match(layout, /name="farm\/create"/);
  assert.match(layout, /name="farm\/select"/);
  assert.match(layout, /name="farm\/details"/);
  assert.match(layout, /name="cattle\/index"/);
  assert.match(layout, /name="cattle\/register"/);
  assert.match(layout, /name="cattle\/\[id\]\/index"/);
  assert.match(layout, /name="cattle\/\[id\]\/edit"/);
  assert.match(layout, /name="feed\/index"/);
  assert.match(layout, /name="feed\/inventory"/);
  assert.match(layout, /name="feed\/records"/);
  assert.match(layout, /name="feed\/nutrition"/);
  assert.match(layout, /name="breeding\/index"/);
  assert.match(layout, /name="breeding\/pregnancy"/);
  assert.match(layout, /name="breeding\/pedigree"/);
  assert.match(sessionRoute, /Redirect/);
  assert.match(dashboardRoute, /DashboardScreen/);
  assert.match(farmRoute, /FarmModuleScreen/);
  assert.match(createFarmRoute, /FarmCreateScreen/);
  assert.match(layout, /name="profile"/);
  assert.match(layout, /name="auth\/verify-email"/);
  const resetPasswordRoute = await readFile(
    path.join(projectRoot, 'app', 'reset-password.jsx'),
    'utf8',
  );
  assert.match(resetPasswordRoute, /useLocalSearchParams/);
  assert.match(resetPasswordRoute, /useState\(typeof rawToken/);
  assert.match(resetPasswordRoute, /setParams\(\{ token: undefined \}\)/);
});

test('authentication screens contain no insecure persistence or sensitive logging', async () => {
  const authDirectory = path.join(projectRoot, 'src', 'features', 'auth');
  const files = (await walk(authDirectory)).filter((file) => /\.(js|jsx)$/.test(file));
  const sources = await Promise.all(files.map((file) => readFile(file, 'utf8')));
  const combined = sources.join('\n');

  assert.doesNotMatch(combined, /AsyncStorage|localStorage|sessionStorage/);
  assert.doesNotMatch(combined, /console\.(log|debug|info|warn|error)/);
  assert.doesNotMatch(combined, /refresh[_-]?token/i);
});

test('auth routes render real screens instead of Step 19.4 placeholders', async () => {
  const loginRoute = await readFile(path.join(projectRoot, 'app', 'auth', 'login.jsx'), 'utf8');
  const signupRoute = await readFile(path.join(projectRoot, 'app', 'auth', 'signup.jsx'), 'utf8');

  assert.match(loginRoute, /LoginScreen/);
  assert.match(signupRoute, /SignupScreen/);
  assert.doesNotMatch(`${loginRoute}\n${signupRoute}`, /AuthComingSoonScreen/);
});
