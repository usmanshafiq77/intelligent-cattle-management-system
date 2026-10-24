import { act, render, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";

import { ApiError } from "../src/api/errors";
import {
  resetAuthTransportForTests,
  signalSessionExpired,
  subscribeToSessionExpiration,
} from "../src/api/authTransport";
import { requireCurrentUserResponse } from "../src/features/auth/authContracts";
import { AuthProvider, useAuth } from "../src/features/auth/context/AuthProvider";
import { createSecureTokenStore } from "../src/features/auth/storage/secureTokenStore";
import { canAccessProtectedRoutes, canAccessPublicAuthRoutes } from "../src/navigation/sessionPolicy";

const USER = Object.freeze({
  id: "2e55bff7-9ce0-49a7-8c39-b3a9cbcb86c4",
  full_name: "Farm Owner",
  email: "owner@example.com",
  is_system_admin: false,
  status: "ACTIVE",
  is_email_verified: true,
  created_at: "2026-10-16T10:00:00Z",
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function createTransport(initialToken = null) {
  let token = initialToken;
  let expirationListener = null;
  return {
    configureAuthTokenProvider: jest.fn(),
    getAccessToken: jest.fn(async () => token),
    setAccessToken: jest.fn(async (nextToken) => { token = nextToken; }),
    removeAccessToken: jest.fn(async () => { token = null; }),
    subscribeToSessionExpiration: jest.fn((listener) => {
      expirationListener = listener;
      return jest.fn();
    }),
    emitExpiration: (expiredToken) => expirationListener?.({ reason: "unauthorized", token: expiredToken }),
    currentToken: () => token,
  };
}

let latestAuth;
function SessionProbe() {
  latestAuth = useAuth();
  return <Text testID="status">{latestAuth.status}</Text>;
}

function mountProvider({ transport = createTransport(), api = { getCurrentUser: jest.fn() } } = {}) {
  const tokenProvider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  const screen = render(
    <AuthProvider transport={transport} tokenProvider={tokenProvider} api={api}>
      <SessionProbe />
    </AuthProvider>,
  );
  return { api, screen, transport };
}

async function expectStatus(status) {
  await waitFor(() => expect(latestAuth.status).toBe(status));
}

afterEach(() => {
  resetAuthTransportForTests();
  latestAuth = null;
});

test("web token storage is memory-only and a new browser runtime starts empty", async () => {
  const secureStore = { getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn() };
  const store = createSecureTokenStore({ platform: "web", secureStore });
  await store.setToken(" token-a ");
  await expect(store.getToken()).resolves.toBe("token-a");
  await expect(createSecureTokenStore({ platform: "web", secureStore }).getToken()).resolves.toBeNull();
  await store.removeToken();
  expect(secureStore.getItemAsync).not.toHaveBeenCalled();
  expect(secureStore.setItemAsync).not.toHaveBeenCalled();
  expect(secureStore.deleteItemAsync).not.toHaveBeenCalled();
});

test("native token storage delegates serially to SecureStore and never leaks native errors", async () => {
  const calls = [];
  const secureStore = {
    getItemAsync: jest.fn(async () => { calls.push("get"); return " token-a "; }),
    setItemAsync: jest.fn(async () => { calls.push("set"); }),
    deleteItemAsync: jest.fn(async () => { calls.push("remove"); }),
  };
  const store = createSecureTokenStore({ platform: "android", secureStore, key: "test.key" });
  await Promise.all([store.setToken("token-a"), store.getToken(), store.removeToken()]);
  expect(calls).toEqual(["set", "get", "remove"]);
  expect(secureStore.setItemAsync).toHaveBeenCalledWith("test.key", "token-a");
  await expect(store.setToken(" ")).rejects.toThrow("non-empty");

  secureStore.getItemAsync.mockRejectedValueOnce(new Error("sensitive native detail"));
  const error = await store.getToken().catch((caught) => caught);
  expect(error.message).toBe("Secure token storage is unavailable. Please try again.");
  expect(error.message).not.toContain("sensitive");
});

test.each([
  ["read", "getItemAsync", "getToken"],
  ["write", "setItemAsync", "setToken"],
  ["remove", "deleteItemAsync", "removeToken"],
])("native SecureStore %s failures are explicit", async (operation, method, storeMethod) => {
  const secureStore = { getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn() };
  secureStore[method].mockRejectedValue(new Error("native secret"));
  const store = createSecureTokenStore({ platform: "ios", secureStore });
  const action = storeMethod === "setToken" ? store[storeMethod]("token") : store[storeMethod]();
  const error = await action.catch((caught) => caught);
  expect(error.code).toBe("SECURE_TOKEN_STORAGE_ERROR");
  expect(error.operation).toBe(operation);
});

test("no stored token restores an unauthenticated session without calling auth/me", async () => {
  const { api } = mountProvider();
  await expectStatus("unauthenticated");
  expect(api.getCurrentUser).not.toHaveBeenCalled();
});

test("a stored token becomes authenticated only after validated auth/me hydration", async () => {
  const api = { getCurrentUser: jest.fn().mockResolvedValue(USER) };
  mountProvider({ transport: createTransport("stored-token"), api });
  await expectStatus("authenticated");
  expect(latestAuth.user).toEqual(USER);
  expect(api.getCurrentUser).toHaveBeenCalledTimes(1);
});

test.each([401, 403])("confirmed invalid stored session (%s) is deleted", async (status) => {
  const transport = createTransport("invalid-token");
  const api = { getCurrentUser: jest.fn().mockRejectedValue(new ApiError("Invalid", { status })) };
  mountProvider({ transport, api });
  await expectStatus("unauthenticated");
  expect(transport.removeAccessToken).toHaveBeenCalledTimes(1);
  expect(transport.currentToken()).toBeNull();
});

test.each([
  ["offline", new ApiError("Offline", { code: "NETWORK_ERROR" })],
  ["timeout", new ApiError("Timeout", { code: "TIMEOUT" })],
  ["503", new ApiError("Unavailable", { status: 503 })],
])("%s during auth/me preserves the token and blocks protected state", async (_label, error) => {
  const transport = createTransport("valid-unverified-token");
  mountProvider({ transport, api: { getCurrentUser: jest.fn().mockRejectedValue(error) } });
  await expectStatus("verification-unavailable");
  expect(latestAuth.isAuthenticated).toBe(false);
  expect(transport.removeAccessToken).not.toHaveBeenCalled();
  expect(transport.currentToken()).toBe("valid-unverified-token");
});

test("SecureStore read failure is surfaced without attempting auth/me", async () => {
  const transport = createTransport();
  transport.getAccessToken.mockRejectedValue(new Error("storage failed"));
  const api = { getCurrentUser: jest.fn() };
  mountProvider({ transport, api });
  await expectStatus("verification-unavailable");
  expect(latestAuth.sessionIssue.kind).toBe("storage-read");
  expect(api.getCurrentUser).not.toHaveBeenCalled();
});

test("login persists the validated token and hydrates the current user", async () => {
  const transport = createTransport();
  const api = { getCurrentUser: jest.fn().mockResolvedValue(USER) };
  mountProvider({ transport, api });
  await expectStatus("unauthenticated");
  await act(async () => { await latestAuth.completeLogin({ access_token: "new-token", token_type: "bearer" }); });
  expect(latestAuth.status).toBe("authenticated");
  expect(latestAuth.user).toEqual(USER);
  expect(transport.setAccessToken).toHaveBeenCalledWith("new-token");
});

test("login storage failure never authenticates and is surfaced safely", async () => {
  const transport = createTransport();
  transport.setAccessToken.mockRejectedValue(new Error("write failed"));
  mountProvider({ transport });
  await expectStatus("unauthenticated");
  await act(async () => {
    await expect(latestAuth.completeLogin({ access_token: "new-token", token_type: "bearer" })).rejects.toThrow("write failed");
  });
  await expectStatus("verification-unavailable");
  expect(latestAuth.sessionIssue.kind).toBe("storage-write");
});

test("manual logout clears user and credentials; deletion failure cannot claim success", async () => {
  const transport = createTransport("token");
  mountProvider({ transport, api: { getCurrentUser: jest.fn().mockResolvedValue(USER) } });
  await expectStatus("authenticated");
  await act(async () => { await latestAuth.logout(); });
  expect(latestAuth.status).toBe("unauthenticated");
  expect(latestAuth.user).toBeNull();

  transport.removeAccessToken.mockRejectedValueOnce(new Error("delete failed"));
  await act(async () => { await expect(latestAuth.logout()).rejects.toThrow("could not confirm"); });
  await expectStatus("verification-unavailable");
  expect(latestAuth.sessionIssue.kind).toBe("storage-remove");
});

test("logout during pending restoration prevents late authentication", async () => {
  const verification = deferred();
  const transport = createTransport("stored-token");
  mountProvider({ transport, api: { getCurrentUser: jest.fn(() => verification.promise) } });
  await waitFor(() => expect(transport.getAccessToken).toHaveBeenCalled());
  await act(async () => { await latestAuth.logout(); });
  verification.resolve(USER);
  await act(async () => { await verification.promise; });
  expect(latestAuth.status).toBe("unauthenticated");
});

test("logout during profile refresh prevents stale user data from returning", async () => {
  const refreshed = deferred();
  const transport = createTransport("stored-token");
  const api = { getCurrentUser: jest.fn().mockResolvedValueOnce(USER).mockImplementationOnce(() => refreshed.promise) };
  mountProvider({ transport, api });
  await expectStatus("authenticated");
  let refresh;
  await act(async () => {
    refresh = latestAuth.refreshProfile();
    await Promise.resolve();
  });
  await act(async () => { await latestAuth.logout(); });
  refreshed.resolve({ ...USER, full_name: "Stale user" });
  await act(async () => { await refresh; });
  expect(latestAuth.status).toBe("unauthenticated");
  expect(latestAuth.user).toBeNull();
});

test("logout during a pending login wins after the queued credential write", async () => {
  const write = deferred();
  const transport = createTransport();
  transport.setAccessToken.mockImplementation(() => write.promise);
  const api = { getCurrentUser: jest.fn().mockResolvedValue(USER) };
  mountProvider({ transport, api });
  await expectStatus("unauthenticated");
  let login;
  let logout;
  await act(async () => {
    login = latestAuth.completeLogin({ access_token: "token-a", token_type: "bearer" });
    logout = latestAuth.logout();
    await Promise.resolve();
  });
  write.resolve();
  await act(async () => { await Promise.all([login, logout]); });
  expect(latestAuth.status).toBe("unauthenticated");
  expect(api.getCurrentUser).not.toHaveBeenCalled();
});

test("a newer login wins when an older auth/me response arrives late", async () => {
  const firstVerification = deferred();
  const secondUser = { ...USER, id: "f5ad18ac-6ad4-4ea0-9804-748551d53c4f", email: "new@example.com" };
  const api = { getCurrentUser: jest.fn().mockImplementationOnce(() => firstVerification.promise).mockResolvedValueOnce(secondUser) };
  const transport = createTransport();
  mountProvider({ transport, api });
  await expectStatus("unauthenticated");
  let firstLogin;
  await act(async () => {
    firstLogin = latestAuth.completeLogin({ access_token: "token-a", token_type: "bearer" });
    await Promise.resolve();
  });
  await waitFor(() => expect(api.getCurrentUser).toHaveBeenCalledTimes(1));
  await act(async () => { await latestAuth.completeLogin({ access_token: "token-b", token_type: "bearer" }); });
  firstVerification.resolve(USER);
  await act(async () => { await firstLogin; });
  expect(latestAuth.user).toEqual(secondUser);
  expect(latestAuth.status).toBe("authenticated");
});

test("a late 401 for an old token cannot clear a newer authenticated session", async () => {
  const transport = createTransport("old-token");
  const api = { getCurrentUser: jest.fn().mockResolvedValue(USER) };
  mountProvider({ transport, api });
  await expectStatus("authenticated");
  await act(async () => { await latestAuth.completeLogin({ access_token: "new-token", token_type: "bearer" }); });
  transport.removeAccessToken.mockClear();
  await act(async () => { transport.emitExpiration("old-token"); await Promise.resolve(); });
  expect(transport.removeAccessToken).not.toHaveBeenCalled();
  expect(latestAuth.status).toBe("authenticated");
});

test("repeated 401 signals for one token notify expiration listeners once", () => {
  const listener = jest.fn();
  const unsubscribe = subscribeToSessionExpiration(listener);
  signalSessionExpired("same-token");
  signalSessionExpired("same-token");
  expect(listener).toHaveBeenCalledTimes(1);
  expect(listener).toHaveBeenCalledWith({ reason: "unauthorized", token: "same-token" });
  unsubscribe();
});

test("current-user validation rejects incomplete private data", () => {
  expect(() => requireCurrentUserResponse({ ...USER, email: null })).toThrow("current-user response");
  expect(requireCurrentUserResponse(USER)).toEqual(USER);
});

test("route policy denies protected routes until verified and hides public auth routes after login", () => {
  expect(canAccessProtectedRoutes("initializing")).toBe(false);
  expect(canAccessProtectedRoutes("verification-unavailable")).toBe(false);
  expect(canAccessProtectedRoutes("unauthenticated")).toBe(false);
  expect(canAccessProtectedRoutes("authenticated")).toBe(true);
  expect(canAccessPublicAuthRoutes("unauthenticated")).toBe(true);
  expect(canAccessPublicAuthRoutes("authenticated")).toBe(false);
});
