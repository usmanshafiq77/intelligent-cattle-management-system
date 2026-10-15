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
    'src/api/client.js',
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

test('environment example contains a public URL and no credentials', async () => {
  const example = await readFile(path.join(projectRoot, '.env.example'), 'utf8');

  assert.match(example, /^EXPO_PUBLIC_API_BASE_URL=/m);
  assert.doesNotMatch(example, /(password|secret|token|api_key)\s*=/i);
});
