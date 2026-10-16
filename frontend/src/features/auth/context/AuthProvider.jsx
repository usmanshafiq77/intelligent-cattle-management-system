import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { configureAuthTokenProvider, removeAccessToken, setAccessToken } from "../../../api/authTransport";
import { requireLoginResponse } from "../authContracts";
import { initializeSecureTokenStorage } from "../storage/secureTokenStore";

const AuthContext = createContext(null);

const defaultTransport = Object.freeze({
  configureAuthTokenProvider,
  removeAccessToken,
  setAccessToken,
});

export function AuthProvider({ children, tokenProvider, transport = defaultTransport }) {
  const initialized = useRef(false);
  const operation = useRef(0);
  const [status, setStatus] = useState("unauthenticated");
  const [user, setUser] = useState(null);

  if (!initialized.current) {
    const provider = tokenProvider || initializeSecureTokenStorage({ configure: transport.configureAuthTokenProvider });
    if (tokenProvider) transport.configureAuthTokenProvider(provider);
    initialized.current = true;
  }

  const clearSession = useCallback(async () => {
    const currentOperation = ++operation.current;
    try {
      await transport.removeAccessToken();
    } finally {
      if (operation.current === currentOperation) {
        setUser(null);
        setStatus("unauthenticated");
      }
    }
  }, [transport]);

  const completeLogin = useCallback(async (response) => {
    const login = requireLoginResponse(response);
    const currentOperation = ++operation.current;
    await transport.setAccessToken(login.accessToken);
    if (operation.current !== currentOperation) return { cancelled: true };
    setUser(null);
    setStatus("authenticated");
    return { cancelled: false };
  }, [transport]);

  const value = useMemo(() => ({
    status,
    user,
    isAuthenticated: status === "authenticated",
    completeLogin,
    clearSession,
    logout: clearSession,
  }), [clearSession, completeLogin, status, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}

export function useOptionalAuth() {
  return useContext(AuthContext);
}
