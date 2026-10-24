import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { AuthProvider, useAuth } from "../src/features/auth/context/AuthProvider";
import { ProfileScreen } from "../src/features/auth/screens/ProfileScreen";
import { VerificationScreen } from "../src/features/auth/screens/VerificationScreen";
import { ThemeProvider } from "../src/theme/ThemeProvider";

const USER = Object.freeze({
  id: "2e55bff7-9ce0-49a7-8c39-b3a9cbcb86c4",
  full_name: "Farm Owner",
  email: "owner@example.com",
  is_system_admin: false,
  status: "ACTIVE",
  is_email_verified: true,
  created_at: "2026-10-16T10:00:00Z",
});

function createTransport(token = "token") {
  let current = token;
  return {
    configureAuthTokenProvider: jest.fn(),
    getAccessToken: jest.fn(async () => current),
    setAccessToken: jest.fn(async (value) => { current = value; }),
    removeAccessToken: jest.fn(async () => { current = null; }),
    subscribeToSessionExpiration: jest.fn(() => jest.fn()),
  };
}

function renderProfile({ user = USER, api = { getCurrentUser: jest.fn().mockResolvedValue(user) }, transport = createTransport(), onVerify = jest.fn() } = {}) {
  const provider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  return {
    onVerify,
    transport,
    ...render(
      <ThemeProvider persistPreference={false}>
        <AuthProvider transport={transport} tokenProvider={provider} api={api}>
          <ProfileScreen onVerify={onVerify} />
        </AuthProvider>
      </ThemeProvider>,
    ),
  };
}

function renderVerification(props = {}) {
  return render(
    <ThemeProvider persistPreference={false}>
      <VerificationScreen onBack={jest.fn()} {...props} />
    </ThemeProvider>,
  );
}

test("profile renders verified server user data with no hardcoded identity", async () => {
  const screen = renderProfile();
  await waitFor(() => expect(screen.getByText("Farm Owner")).toBeTruthy());
  expect(screen.getAllByText("owner@example.com")).toHaveLength(2);
  expect(screen.getByLabelText("Status: Email verified")).toBeTruthy();
  expect(screen.getByLabelText("Status: Active account")).toBeTruthy();
  expect(screen.getByText(/Profile editing and password changes are unavailable/)).toBeTruthy();
  expect(screen.queryByText("John Doe")).toBeNull();
});

test("profile renders unverified status and opens real verification navigation", async () => {
  const onVerify = jest.fn();
  const screen = renderProfile({ user: { ...USER, is_email_verified: false }, onVerify });
  await waitFor(() => expect(screen.getByLabelText("Status: Email verification needed")).toBeTruthy());
  fireEvent.press(screen.getByText("Verify Email"));
  expect(onVerify).toHaveBeenCalledTimes(1);
});

test("profile maps an inactive status accurately without inventing a role", async () => {
  const screen = renderProfile({ user: { ...USER, status: "INACTIVE", is_email_verified: false } });
  await waitFor(() => expect(screen.getByLabelText("Status: Inactive account")).toBeTruthy());
  expect(screen.queryByText(/Owner role/)).toBeNull();
});

test("profile refresh hydrates current server data and logout clears credentials", async () => {
  const changedUser = { ...USER, full_name: "Updated Owner" };
  const api = { getCurrentUser: jest.fn().mockResolvedValueOnce(USER).mockResolvedValueOnce(changedUser) };
  const transport = createTransport();
  const screen = renderProfile({ api, transport });
  await waitFor(() => expect(screen.getByText("Farm Owner")).toBeTruthy());
  fireEvent.press(screen.getByTestId("profile-refresh"));
  await waitFor(() => expect(screen.getByText("Updated Owner")).toBeTruthy());
  fireEvent.press(screen.getByTestId("profile-logout"));
  await waitFor(() => expect(transport.removeAccessToken).toHaveBeenCalledTimes(1));
});

test("profile never presents stale private data after refresh failure", async () => {
  const api = { getCurrentUser: jest.fn().mockResolvedValue(USER) };
  const screen = renderProfile({ api });
  await waitFor(() => expect(screen.getByText("Farm Owner")).toBeTruthy());
  api.getCurrentUser.mockRejectedValueOnce(new ApiError("Offline", { code: "NETWORK_ERROR" }));
  fireEvent.press(screen.getByTestId("profile-refresh"));
  await waitFor(() => expect(api.getCurrentUser).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.queryByText("Farm Owner")).toBeNull());
});

test("verification sends only the entered one-time token and clears it after success", async () => {
  const api = { verifyEmail: jest.fn().mockResolvedValue({ detail: "Email verified successfully" }), resendVerification: jest.fn() };
  const screen = renderVerification({ api });
  fireEvent.changeText(screen.getByTestId("verification-token"), " one-time-token ");
  fireEvent.press(screen.getByTestId("verify-email-submit"));
  await waitFor(() => expect(screen.getByText(/Email verified successfully/)).toBeTruthy());
  expect(api.verifyEmail).toHaveBeenCalledWith("one-time-token", { signal: expect.any(Object) });
  expect(screen.getByTestId("verification-token").props.value).toBe("");
});

test("verification deep link automatically submits its token once", async () => {
  const api = { verifyEmail: jest.fn().mockResolvedValue({ detail: "Email verified successfully" }), resendVerification: jest.fn() };
  const screen = renderVerification({ api, initialToken: " deep-link-token " });
  await waitFor(() => expect(api.verifyEmail).toHaveBeenCalledWith("deep-link-token", { signal: expect.any(Object) }));
  expect(api.verifyEmail).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(screen.getByText(/Email verified successfully/)).toBeTruthy());
  expect(screen.getByTestId("verification-token").props.value).toBe("");
});

test("verification refreshes the authenticated account status after success", async () => {
  const transport = createTransport();
  const api = {
    getCurrentUser: jest.fn().mockResolvedValueOnce({ ...USER, is_email_verified: false }).mockResolvedValueOnce(USER),
    verifyEmail: jest.fn().mockResolvedValue({ detail: "Email verified successfully" }),
    resendVerification: jest.fn(),
  };
  let auth;
  function Probe() {
    auth = useAuth();
    return <VerificationScreen api={api} onBack={jest.fn()} />;
  }
  const provider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  const screen = render(<ThemeProvider persistPreference={false}><AuthProvider transport={transport} tokenProvider={provider} api={api}><Probe /></AuthProvider></ThemeProvider>);
  await waitFor(() => expect(auth.user?.is_email_verified).toBe(false));
  fireEvent.changeText(screen.getByTestId("verification-token"), "one-time-token");
  fireEvent.press(screen.getByTestId("verify-email-submit"));
  await waitFor(() => expect(auth.user?.is_email_verified).toBe(true));
});

test.each([
  [new ApiError("Invalid", { status: 400 }), /invalid, expired, or has already been used/],
  [new ApiError("Offline", { code: "NETWORK_ERROR" }), /cannot reach the server/],
])("verification shows safe recoverable failures", async (error, expected) => {
  const api = { verifyEmail: jest.fn().mockRejectedValue(error), resendVerification: jest.fn() };
  const screen = renderVerification({ api });
  fireEvent.changeText(screen.getByTestId("verification-token"), "one-time-token");
  fireEvent.press(screen.getByTestId("verify-email-submit"));
  await waitFor(() => expect(screen.getByText(expected)).toBeTruthy());
});

test("verification prevents duplicate submission", async () => {
  let resolveVerification;
  const api = {
    verifyEmail: jest.fn(() => new Promise((resolve) => { resolveVerification = resolve; })),
    resendVerification: jest.fn(),
  };
  const screen = renderVerification({ api });
  fireEvent.changeText(screen.getByTestId("verification-token"), "one-time-token");
  fireEvent.press(screen.getByTestId("verify-email-submit"));
  fireEvent.press(screen.getByTestId("verify-email-submit"));
  expect(api.verifyEmail).toHaveBeenCalledTimes(1);
  await act(async () => resolveVerification({ detail: "Email verified successfully" }));
});

test("resend uses an enumeration-safe success message and normalizes email", async () => {
  const api = { verifyEmail: jest.fn(), resendVerification: jest.fn().mockResolvedValue({ detail: "generic" }) };
  const screen = renderVerification({ api });
  fireEvent.changeText(screen.getByTestId("verification-resend-email"), " Owner@Example.COM ");
  fireEvent.press(screen.getByTestId("resend-verification-submit"));
  await waitFor(() => expect(screen.getByText(/If this account exists/)).toBeTruthy());
  expect(api.resendVerification).toHaveBeenCalledWith("owner@example.com", { signal: expect.any(Object) });
});

test("resend rate limiting gives safe cooldown feedback", async () => {
  const api = { verifyEmail: jest.fn(), resendVerification: jest.fn().mockRejectedValue(new ApiError("Rate limited", { status: 429, retryAfterSeconds: 5 })) };
  const screen = renderVerification({ api });
  fireEvent.changeText(screen.getByTestId("verification-resend-email"), "owner@example.com");
  fireEvent.press(screen.getByTestId("resend-verification-submit"));
  await waitFor(() => expect(screen.getByText(/Too many verification requests/)).toBeTruthy());
  expect(screen.getByText(/Try Again in [1-5]s/)).toBeTruthy();
});
