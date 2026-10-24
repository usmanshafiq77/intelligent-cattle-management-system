import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { authApi } from "../../../api/auth";
import {
  configureAuthTokenProvider,
  getAccessToken,
  removeAccessToken,
  setAccessToken,
  subscribeToSessionExpiration,
} from "../../../api/authTransport";
import { requireCurrentUserResponse, requireLoginResponse } from "../authContracts";
import { initializeSecureTokenStorage } from "../storage/secureTokenStore";

const AuthContext = createContext(null);

const defaultTransport = Object.freeze({
  configureAuthTokenProvider,
  getAccessToken,
  removeAccessToken,
  setAccessToken,
  subscribeToSessionExpiration,
});

const SESSION_MESSAGES = Object.freeze({
  verification: "Your saved session could not be verified. Check the connection and try again.",
  storageRead: "Secure session storage could not be read. Try again before continuing.",
  storageWrite: "The session could not be saved securely. Please try logging in again.",
  storageRemove: "ICMS could not confirm that the saved credential was removed. Try signing out again.",
});

function isInvalidSession(error) {
  return error?.status === 401 || error?.status === 403;
}

export function AuthProvider({
  children,
  tokenProvider,
  transport = defaultTransport,
  api = authApi,
}) {
  const initialized = useRef(false);
  const mounted = useRef(false);
  const operation = useRef(0);
  const removalInFlight = useRef(null);
  const [status, setStatus] = useState("initializing");
  const [user, setUser] = useState(null);
  const [sessionIssue, setSessionIssue] = useState(null);
  const [isProfileRefreshing, setIsProfileRefreshing] = useState(false);

  if (!initialized.current) {
    const provider = tokenProvider || initializeSecureTokenStorage({ configure: transport.configureAuthTokenProvider });
    if (tokenProvider) transport.configureAuthTokenProvider(provider);
    initialized.current = true;
  }

  const updateIfCurrent = useCallback((currentOperation, update) => {
    if (mounted.current && operation.current === currentOperation) update();
  }, []);

  const markUnavailable = useCallback((currentOperation, kind, message) => {
    updateIfCurrent(currentOperation, () => {
      setUser(null);
      setSessionIssue({ kind, message });
      setStatus("verification-unavailable");
    });
  }, [updateIfCurrent]);

  const removeCredential = useCallback(async (currentOperation) => {
    try {
      if (!removalInFlight.current) {
        let wrappedRemoval;
        wrappedRemoval = Promise.resolve().then(() => transport.removeAccessToken()).finally(() => {
          if (removalInFlight.current === wrappedRemoval) removalInFlight.current = null;
        });
        removalInFlight.current = wrappedRemoval;
      }
      await removalInFlight.current;
      return true;
    } catch {
      markUnavailable(currentOperation, "storage-remove", SESSION_MESSAGES.storageRemove);
      return false;
    }
  }, [markUnavailable, transport]);

  const verifyCurrentUser = useCallback(async (currentOperation, { propagate = false } = {}) => {
    try {
      const currentUser = requireCurrentUserResponse(await api.getCurrentUser());
      if (operation.current !== currentOperation || !mounted.current) return { cancelled: true };
      updateIfCurrent(currentOperation, () => {
        setUser(currentUser);
        setSessionIssue(null);
        setStatus("authenticated");
      });
      return { authenticated: true, user: currentUser };
    } catch (error) {
      if (operation.current !== currentOperation || !mounted.current) return { cancelled: true };
      if (isInvalidSession(error)) {
        const removed = await removeCredential(currentOperation);
        if (removed) {
          updateIfCurrent(currentOperation, () => {
            setUser(null);
            setSessionIssue(null);
            setStatus("unauthenticated");
          });
        }
      } else {
        markUnavailable(currentOperation, "verification", SESSION_MESSAGES.verification);
      }
      if (propagate) throw error;
      return { authenticated: false, error };
    }
  }, [api, markUnavailable, removeCredential, updateIfCurrent]);

  const restoreSession = useCallback(async () => {
    const currentOperation = ++operation.current;
    updateIfCurrent(currentOperation, () => {
      setStatus("initializing");
      setSessionIssue(null);
    });
    let token;
    try {
      token = await transport.getAccessToken();
    } catch {
      markUnavailable(currentOperation, "storage-read", SESSION_MESSAGES.storageRead);
      return { authenticated: false };
    }
    if (operation.current !== currentOperation || !mounted.current) return { cancelled: true };
    if (!token) {
      updateIfCurrent(currentOperation, () => {
        setUser(null);
        setSessionIssue(null);
        setStatus("unauthenticated");
      });
      return { authenticated: false };
    }
    return verifyCurrentUser(currentOperation);
  }, [markUnavailable, transport, updateIfCurrent, verifyCurrentUser]);

  const completeLogin = useCallback(async (response) => {
    const login = requireLoginResponse(response);
    const currentOperation = ++operation.current;
    updateIfCurrent(currentOperation, () => {
      setUser(null);
      setSessionIssue(null);
      setStatus("initializing");
    });
    try {
      await transport.setAccessToken(login.accessToken);
    } catch (error) {
      markUnavailable(currentOperation, "storage-write", SESSION_MESSAGES.storageWrite);
      throw error;
    }
    if (operation.current !== currentOperation || !mounted.current) return { cancelled: true };
    return verifyCurrentUser(currentOperation, { propagate: true });
  }, [markUnavailable, transport, updateIfCurrent, verifyCurrentUser]);

  const clearSession = useCallback(async () => {
    const currentOperation = ++operation.current;
    updateIfCurrent(currentOperation, () => {
      setUser(null);
      setSessionIssue(null);
      setStatus("initializing");
    });
    const removed = await removeCredential(currentOperation);
    if (!removed) throw new Error(SESSION_MESSAGES.storageRemove);
    updateIfCurrent(currentOperation, () => {
      setUser(null);
      setSessionIssue(null);
      setStatus("unauthenticated");
    });
    return { cleared: true };
  }, [removeCredential, updateIfCurrent]);

  const refreshProfile = useCallback(async () => {
    const currentOperation = ++operation.current;
    updateIfCurrent(currentOperation, () => setIsProfileRefreshing(true));
    try {
      return await verifyCurrentUser(currentOperation, { propagate: true });
    } finally {
      updateIfCurrent(currentOperation, () => setIsProfileRefreshing(false));
    }
  }, [updateIfCurrent, verifyCurrentUser]);

  useEffect(() => {
    mounted.current = true;
    void restoreSession();
    const unsubscribe = transport.subscribeToSessionExpiration(({ token }) => {
      const observedOperation = operation.current;
      void (async () => {
        try {
          const currentToken = await transport.getAccessToken();
          if (!mounted.current || operation.current !== observedOperation || !token || token !== currentToken) return;
          const currentOperation = ++operation.current;
          const removed = await removeCredential(currentOperation);
          if (removed) {
            updateIfCurrent(currentOperation, () => {
              setUser(null);
              setSessionIssue(null);
              setStatus("unauthenticated");
            });
          }
        } catch {
          if (mounted.current && operation.current === observedOperation) {
            markUnavailable(observedOperation, "storage-read", SESSION_MESSAGES.storageRead);
          }
        }
      })();
    });
    return () => {
      mounted.current = false;
      operation.current += 1;
      unsubscribe();
    };
  }, [markUnavailable, removeCredential, restoreSession, transport, updateIfCurrent]);

  const value = useMemo(() => ({
    status,
    user,
    sessionIssue,
    isAuthenticated: status === "authenticated",
    isInitializing: status === "initializing",
    isProfileRefreshing,
    completeLogin,
    restoreSession,
    retryVerification: restoreSession,
    clearSession,
    logout: clearSession,
    refreshProfile,
  }), [clearSession, completeLogin, isProfileRefreshing, refreshProfile, restoreSession, sessionIssue, status, user]);

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
