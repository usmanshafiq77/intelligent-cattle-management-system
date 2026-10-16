import { API_DEBUG_ENABLED, requireApiBaseUrl } from "../config/environment";
import { getAccessToken, signalSessionExpired } from "./authTransport";
import { ApiError, cancellationError, httpError, networkError, timeoutError } from "./errors";

export const API_PREFIX = "/api/v1";
export const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
export const DEFAULT_UPLOAD_TIMEOUT_MS = 60000;

export function serializeQuery(query = {}) {
  const parts = [];
  Object.entries(query).forEach(([key, rawValue]) => {
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    values.forEach((value) => {
      if (value === undefined || value === null || value === "") return;
      const serialized = value instanceof Date ? value.toISOString() : String(value);
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(serialized)}`);
    });
  });
  return parts.join("&");
}

export function buildApiUrl(path, { query, baseUrl = requireApiBaseUrl() } = {}) {
  if (typeof path !== "string" || !path.trim() || path.includes("://")) {
    throw new TypeError("API paths must be non-empty relative paths.");
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const queryString = serializeQuery(query);
  return `${baseUrl}${API_PREFIX}${normalizedPath}${queryString ? `?${queryString}` : ""}`;
}

async function parseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function debugRequest(logger, enabled, event, details) {
  if (!enabled || typeof logger !== "function") return;
  logger(`[ICMS API] ${event}`, details);
}

export function createMultipartBody(fields = {}) {
  const form = new FormData();
  Object.entries(fields).forEach(([key, rawValue]) => {
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    values.forEach((value) => {
      if (value !== undefined && value !== null) form.append(key, value);
    });
  });
  return form;
}

export function createApiClient({
  fetchImpl = (...args) => globalThis.fetch(...args),
  baseUrlResolver = requireApiBaseUrl,
  tokenGetter = getAccessToken,
  unauthorizedHandler = signalSessionExpired,
  debug = API_DEBUG_ENABLED,
  logger = console.debug,
} = {}) {
  async function request(path, options = {}) {
    const {
      method = "GET",
      query,
      json,
      body,
      headers = {},
      auth = true,
      timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
      signal,
      responseType = "json",
    } = options;

    if (json !== undefined && body !== undefined) {
      throw new TypeError("Provide either json or body, not both.");
    }
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new TypeError("Request timeout must be a positive number.");
    }

    const upperMethod = method.toUpperCase();
    const token = auth ? await tokenGetter() : null;
    const requestHeaders = {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    };
    const controller = new AbortController();
    let timedOut = false;
    const cancel = () => controller.abort();
    if (signal?.aborted) throw cancellationError();
    signal?.addEventListener?.("abort", cancel, { once: true });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const startedAt = Date.now();
    const url = buildApiUrl(path, { query, baseUrl: baseUrlResolver() });

    debugRequest(logger, debug, "request", { method: upperMethod, path });

    try {
      const response = await fetchImpl(url, {
        method: upperMethod,
        headers: requestHeaders,
        body: json !== undefined ? JSON.stringify(json) : body,
        signal: controller.signal,
      });
      debugRequest(logger, debug, "response", {
        method: upperMethod,
        path,
        status: response.status,
        durationMs: Date.now() - startedAt,
      });

      if (!response.ok) {
        const payload = await parseJson(response);
        const error = httpError(response.status, payload, response.headers);
        if (response.status === 401 && token) unauthorizedHandler(token);
        throw error;
      }
      if (response.status === 204) return null;
      if (responseType === "blob") return response.blob();
      if (responseType === "text") return response.text();
      if (responseType === "response") return response;
      return parseJson(response);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (timedOut) throw timeoutError(timeoutMs, error);
      if (signal?.aborted || error?.name === "AbortError") throw cancellationError(error);
      throw networkError(error);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener?.("abort", cancel);
    }
  }

  return Object.freeze({
    request,
    get: (path, options) => request(path, { ...options, method: "GET" }),
    post: (path, options) => request(path, { ...options, method: "POST" }),
    put: (path, options) => request(path, { ...options, method: "PUT" }),
    patch: (path, options) => request(path, { ...options, method: "PATCH" }),
    delete: (path, options) => request(path, { ...options, method: "DELETE" }),
  });
}

export const apiClient = createApiClient();
export const apiRequest = apiClient.request;
