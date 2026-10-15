const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

export const API_BASE_URL = configuredApiBaseUrl
  ? configuredApiBaseUrl.replace(/\/+$/, '')
  : null;

export function requireApiBaseUrl() {
  if (!API_BASE_URL) {
    throw new Error(
      'EXPO_PUBLIC_API_BASE_URL is not configured. Copy .env.example to .env and set a reachable FastAPI host.',
    );
  }

  return API_BASE_URL;
}
