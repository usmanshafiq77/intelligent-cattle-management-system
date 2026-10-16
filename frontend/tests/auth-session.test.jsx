import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Text, View } from "react-native";

import { AuthProvider, useAuth } from "../src/features/auth/context/AuthProvider";
import { createSecureTokenStore } from "../src/features/auth/storage/secureTokenStore";

function SessionProbe() {
  const auth = useAuth();
  return (
    <View>
      <Text testID="status">{auth.status}</Text>
      <Text testID="authenticated">{String(auth.isAuthenticated)}</Text>
      <Text testID="user">{String(auth.user)}</Text>
      <Text testID="login" onPress={() => auth.completeLogin({ access_token: "token-a", token_type: "bearer" })}>Login</Text>
      <Text testID="logout" onPress={() => auth.logout()}>Logout</Text>
    </View>
  );
}

function createTransport() {
  return {
    configureAuthTokenProvider: jest.fn(),
    setAccessToken: jest.fn().mockResolvedValue(undefined),
    removeAccessToken: jest.fn().mockResolvedValue(undefined),
  };
}

test("web token store is memory-only and never calls native secure storage", async () => {
  const secureStore = { getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn() };
  const store = createSecureTokenStore({ platform: "web", secureStore });

  await store.setToken(" token-a ");
  await expect(store.getToken()).resolves.toBe("token-a");
  await store.removeToken();
  await expect(store.getToken()).resolves.toBeNull();

  expect(secureStore.setItemAsync).not.toHaveBeenCalled();
  expect(secureStore.getItemAsync).not.toHaveBeenCalled();
  expect(secureStore.deleteItemAsync).not.toHaveBeenCalled();
});

test("native token store delegates serially to SecureStore and surfaces safe failures", async () => {
  const secureStore = {
    getItemAsync: jest.fn().mockResolvedValue(" token-a "),
    setItemAsync: jest.fn().mockResolvedValue(undefined),
    deleteItemAsync: jest.fn().mockResolvedValue(undefined),
  };
  const store = createSecureTokenStore({ platform: "android", secureStore, key: "test.key" });

  await store.setToken("token-a");
  await expect(store.getToken()).resolves.toBe("token-a");
  await store.removeToken();
  expect(secureStore.setItemAsync).toHaveBeenCalledWith("test.key", "token-a");
  expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("test.key");
  await expect(store.setToken(" ")).rejects.toThrow("non-empty");

  secureStore.getItemAsync.mockRejectedValueOnce(new Error("sensitive native detail"));
  await expect(store.getToken()).rejects.toThrow("Secure token storage is unavailable.");
});

test("AuthProvider owns validated login state and clears credentials on logout", async () => {
  const transport = createTransport();
  const tokenProvider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  const screen = render(<AuthProvider transport={transport} tokenProvider={tokenProvider}><SessionProbe /></AuthProvider>);

  expect(screen.getByTestId("status").children.join("")).toBe("unauthenticated");
  fireEvent.press(screen.getByTestId("login"));
  await waitFor(() => expect(screen.getByTestId("authenticated").children.join("")).toBe("true"));
  expect(transport.setAccessToken).toHaveBeenCalledWith("token-a");
  expect(screen.getByTestId("user").children.join("")).toBe("null");

  fireEvent.press(screen.getByTestId("logout"));
  await waitFor(() => expect(screen.getByTestId("status").children.join("")).toBe("unauthenticated"));
  expect(transport.removeAccessToken).toHaveBeenCalledTimes(1);
});

test("logout wins over an overlapping login and malformed login responses are rejected", async () => {
  let resolveSet;
  const transport = createTransport();
  transport.setAccessToken.mockImplementation(() => new Promise((resolve) => { resolveSet = resolve; }));
  const tokenProvider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  let auth;
  function Capture() {
    auth = useAuth();
    return null;
  }
  render(<AuthProvider transport={transport} tokenProvider={tokenProvider}><Capture /></AuthProvider>);

  await expect(auth.completeLogin({ access_token: "", token_type: "bearer" })).rejects.toThrow("reviewed authentication contract");
  const login = auth.completeLogin({ access_token: "token-a", token_type: "bearer" });
  const logout = auth.logout();
  resolveSet();
  await act(async () => { await Promise.all([login, logout]); });
  expect(auth.status).toBe("unauthenticated");
  expect(auth.isAuthenticated).toBe(false);
});
