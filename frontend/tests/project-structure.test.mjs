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
  assert.equal(packageJson.dependencies['expo-router'], '~57.0.28');
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
    'app/dev/design-system.jsx',
    'assets/branding/icms-mark.svg',
    'src/components/brand/BrandMark.jsx',
    'src/components/brand/FarmIntelligenceGraphic.jsx',
    'src/features/onboarding/screens/WelcomeScreen.jsx',
    'src/features/auth/screens/LoginScreen.jsx',
    'src/features/auth/screens/SignupScreen.jsx',
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
    'src/config/environment.js',
    'src/components/ui/Screen.jsx',
    'src/features/home/screens/WelcomeScreen.jsx',
    'src/navigation/routes.js',
  ];

  for (const relativePath of requiredPaths) {
    const contents = await readFile(path.join(projectRoot, relativePath), 'utf8');
    assert.ok(contents.length > 0, `${relativePath} must not be empty`);
  }

  for (const feature of ['auth', 'farms', 'permissions', 'cattle', 'health', 'milk']) {
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
