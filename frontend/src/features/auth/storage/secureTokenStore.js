import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import { configureAuthTokenProvider } from "../../../api/authTransport";

export const ACCESS_TOKEN_KEY = "icms.access-token.v1";

function requireToken(token) {
  if (typeof token !== "string" || !token.trim()) {
    throw new TypeError("Access token must be a non-empty string.");
  }
  return token.trim();
}

function storageFailure() {
  return new Error("Secure token storage is unavailable. Please try again.");
}

export function createSecureTokenStore({
  platform = Platform.OS,
  secureStore = SecureStore,
  key = ACCESS_TOKEN_KEY,
} = {}) {
  const usesNativeSecureStore = platform === "android" || platform === "ios";
  let memoryToken = null;
  let queue = Promise.resolve();

  const serialize = (operation) => {
    const result = queue.then(operation, operation);
    queue = result.catch(() => {});
    return result;
  };

  return Object.freeze({
    async getToken() {
      return serialize(async () => {
        if (!usesNativeSecureStore) return memoryToken;
        try {
          const token = await secureStore.getItemAsync(key);
          return typeof token === "string" && token.trim() ? token.trim() : null;
        } catch {
          throw storageFailure();
        }
      });
    },
    async setToken(token) {
      const normalized = requireToken(token);
      return serialize(async () => {
        if (!usesNativeSecureStore) {
          memoryToken = normalized;
          return;
        }
        try {
          await secureStore.setItemAsync(key, normalized);
        } catch {
          throw storageFailure();
        }
      });
    },
    async removeToken() {
      return serialize(async () => {
        memoryToken = null;
        if (!usesNativeSecureStore) return;
        try {
          await secureStore.deleteItemAsync(key);
        } catch {
          throw storageFailure();
        }
      });
    },
  });
}

let configuredStore = null;

export function initializeSecureTokenStorage({ configure = configureAuthTokenProvider } = {}) {
  if (!configuredStore) configuredStore = createSecureTokenStore();
  configure(configuredStore);
  return configuredStore;
}

export function resetSecureTokenStorageForTests() {
  configuredStore = null;
}
