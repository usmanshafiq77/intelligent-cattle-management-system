import { Platform } from "react-native";

const rawEnvironment = {
  appEnvironment: process.env.EXPO_PUBLIC_APP_ENV,
  defaultApiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
  webApiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL_WEB,
  androidApiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL_ANDROID,
  apiDebug: process.env.EXPO_PUBLIC_API_DEBUG,
};

export class EnvironmentConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "EnvironmentConfigurationError";
    this.code = "INVALID_API_CONFIGURATION";
  }
}

function clean(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function validateApiBaseUrl(value, { platform = Platform.OS, appEnvironment = "development" } = {}) {
  const candidate = clean(value);
  if (!candidate) return null;

  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new EnvironmentConfigurationError("The configured API base URL is not a valid absolute URL.");
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new EnvironmentConfigurationError("The API base URL must use HTTP or HTTPS.");
  }
  if (parsed.username || parsed.password) {
    throw new EnvironmentConfigurationError("The API base URL must not contain credentials.");
  }
  if ((parsed.pathname && parsed.pathname !== "/") || parsed.search || parsed.hash) {
    throw new EnvironmentConfigurationError(
      "The API base URL must contain only the scheme, hostname, and optional port; /api/v1 is added automatically.",
    );
  }
  if (appEnvironment === "production" && parsed.protocol !== "https:") {
    throw new EnvironmentConfigurationError("Production API connections must use HTTPS.");
  }
  if (platform === "android" && ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname)) {
    throw new EnvironmentConfigurationError(
      "Android cannot reach the development computer through localhost. Use 10.0.2.2 for the Android Studio emulator or the computer's LAN address for a physical device.",
    );
  }

  return `${parsed.protocol}//${parsed.host}`;
}

export function resolveApiBaseUrl({
  platform = Platform.OS,
  appEnvironment = clean(rawEnvironment.appEnvironment) || "development",
  defaultApiBaseUrl = rawEnvironment.defaultApiBaseUrl,
  webApiBaseUrl = rawEnvironment.webApiBaseUrl,
  androidApiBaseUrl = rawEnvironment.androidApiBaseUrl,
} = {}) {
  const platformValue = platform === "web"
    ? clean(webApiBaseUrl)
    : platform === "android"
      ? clean(androidApiBaseUrl)
      : null;

  return validateApiBaseUrl(platformValue || defaultApiBaseUrl, { platform, appEnvironment });
}

export const APP_ENV = clean(rawEnvironment.appEnvironment) || "development";
export const API_BASE_URL = resolveApiBaseUrl({ appEnvironment: APP_ENV });
export const API_DEBUG_ENABLED = APP_ENV === "development" && rawEnvironment.apiDebug !== "false";

export function requireApiBaseUrl() {
  if (!API_BASE_URL) {
    throw new EnvironmentConfigurationError(
      "No API URL is configured for this target. Copy .env.example to .env and set a reachable EXPO_PUBLIC_API_BASE_URL or platform-specific override.",
    );
  }
  return API_BASE_URL;
}
