let volatileToken = null;
let provider = null;
let lastExpiredToken = null;
const expirationListeners = new Set();

function normalizeToken(token) {
  return typeof token === "string" && token.trim() ? token.trim() : null;
}

export function configureAuthTokenProvider(nextProvider) {
  if (nextProvider !== null && typeof nextProvider?.getToken !== "function") {
    throw new TypeError("An authentication token provider must implement getToken().");
  }
  provider = nextProvider;
  volatileToken = null;
  lastExpiredToken = null;
}

export async function getAccessToken() {
  const token = provider ? await provider.getToken() : volatileToken;
  return normalizeToken(token);
}

export async function setAccessToken(token) {
  const normalized = normalizeToken(token);
  if (!normalized) throw new TypeError("Access token must be a non-empty string.");
  if (provider?.setToken) await provider.setToken(normalized);
  else volatileToken = normalized;
  lastExpiredToken = null;
}

export async function removeAccessToken() {
  if (provider?.removeToken) await provider.removeToken();
  else volatileToken = null;
  lastExpiredToken = null;
}

export function subscribeToSessionExpiration(listener) {
  if (typeof listener !== "function") throw new TypeError("Session expiration listener must be a function.");
  expirationListeners.add(listener);
  return () => expirationListeners.delete(listener);
}

export function signalSessionExpired(token) {
  const normalized = normalizeToken(token);
  if (!normalized || normalized === lastExpiredToken) return;
  lastExpiredToken = normalized;
  expirationListeners.forEach((listener) => listener({ reason: "unauthorized" }));
}

export function resetAuthTransportForTests() {
  volatileToken = null;
  provider = null;
  lastExpiredToken = null;
  expirationListeners.clear();
}
