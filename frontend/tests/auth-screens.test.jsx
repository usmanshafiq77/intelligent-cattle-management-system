import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { LoginScreen } from "../src/features/auth/screens/LoginScreen";
import { SignupScreen } from "../src/features/auth/screens/SignupScreen";
import { AuthProvider } from "../src/features/auth/context/AuthProvider";
import { ThemeProvider } from "../src/theme/ThemeProvider";

jest.mock("../src/theme/useAppReducedMotion", () => ({ useAppReducedMotion: () => true }));
jest.mock("../src/components/ui/FadeInView", () => ({
  FadeInView: ({ children, ...props }) => {
    const React = require("react");
    const { View } = require("react-native");
    return React.createElement(View, props, children);
  },
}));

function themed(node) {
  return render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);
}

function fillLogin(screen, email = " Farmer@Example.COM ", password = "ValidPassword123!") {
  fireEvent.changeText(screen.getByTestId("login-email"), email);
  fireEvent.changeText(screen.getByTestId("login-password"), password);
}

function fillSignup(screen) {
  fireEvent.changeText(screen.getByTestId("signup-full-name"), "  Farm Owner  ");
  fireEvent.changeText(screen.getByTestId("signup-email"), " Owner@Example.COM ");
  fireEvent.changeText(screen.getByTestId("signup-password"), "ValidPassword123!");
  fireEvent.changeText(screen.getByTestId("signup-confirm-password"), "ValidPassword123!");
}

test("login renders secure, accessible fields and navigation actions", () => {
  const onBack = jest.fn();
  const onCreateAccount = jest.fn();
  const screen = themed(<LoginScreen onBack={onBack} onCreateAccount={onCreateAccount} api={{ login: jest.fn() }} />);

  expect(screen.getByRole("header", { name: "Welcome Back" })).toBeTruthy();
  expect(screen.getByTestId("login-email").props.autoComplete).toBe("email");
  expect(screen.getByTestId("login-password").props.autoComplete).toBe("current-password");
  expect(screen.getByTestId("login-password").props.secureTextEntry).toBe(true);
  fireEvent.press(screen.getByRole("button", { name: "Show password" }));
  expect(screen.getByTestId("login-password").props.secureTextEntry).toBe(false);
  fireEvent.press(screen.getByRole("link", { name: "Create Account" }));
  fireEvent.press(screen.getByRole("button", { name: "Back to welcome" }));
  expect(onCreateAccount).toHaveBeenCalledTimes(1);
  expect(onBack).toHaveBeenCalledTimes(1);
});

test("signup renders reviewed fields with new-password autofill", () => {
  const screen = themed(<SignupScreen onBack={jest.fn()} onLogIn={jest.fn()} api={{ register: jest.fn() }} />);
  expect(screen.getByRole("header", { name: "Start with ICMS" })).toBeTruthy();
  expect(screen.getByTestId("signup-password").props.autoComplete).toBe("new-password");
  expect(screen.getByTestId("signup-confirm-password").props.secureTextEntry).toBe(true);
});

test("forms announce required, invalid email, short password, and mismatch errors", async () => {
  const login = themed(<LoginScreen onBack={jest.fn()} onCreateAccount={jest.fn()} api={{ login: jest.fn() }} />);
  fireEvent.press(login.getByTestId("login-submit"));
  expect(login.getByText("Email address is required.")).toBeTruthy();
  expect(login.getByText("Password is required.")).toBeTruthy();
  login.unmount();

  const signup = themed(<SignupScreen onBack={jest.fn()} onLogIn={jest.fn()} api={{ register: jest.fn() }} />);
  fireEvent.changeText(signup.getByTestId("signup-full-name"), "A");
  fireEvent.changeText(signup.getByTestId("signup-email"), "not-an-email");
  fireEvent.changeText(signup.getByTestId("signup-password"), "short");
  fireEvent.changeText(signup.getByTestId("signup-confirm-password"), "different");
  fireEvent.press(signup.getByTestId("signup-submit"));
  expect(signup.getByText(/Full name must contain/)).toBeTruthy();
  expect(signup.getByText("Enter a valid email address.")).toBeTruthy();
  expect(signup.getByText(/at least 8/)).toBeTruthy();
  expect(signup.getByText("Passwords do not match.")).toBeTruthy();
});

test("login submits normalized JSON, stores only an ephemeral token, and shows honest success", async () => {
  const api = { login: jest.fn().mockResolvedValue({ access_token: "private-token", token_type: "bearer" }) };
  const tokenSetter = jest.fn().mockResolvedValue(undefined);
  const debug = jest.spyOn(console, "debug").mockImplementation(() => {});
  const log = jest.spyOn(console, "log").mockImplementation(() => {});
  const screen = themed(<LoginScreen onBack={jest.fn()} onCreateAccount={jest.fn()} api={api} tokenSetter={tokenSetter} />);
  fillLogin(screen);
  fireEvent.press(screen.getByTestId("login-submit"));

  await waitFor(() => expect(screen.getByText("Login successful")).toBeTruthy());
  expect(api.login).toHaveBeenCalledWith(
    { email: "farmer@example.com", password: "ValidPassword123!" },
    { signal: expect.any(Object) },
  );
  expect(tokenSetter).toHaveBeenCalledWith("private-token");
  expect(JSON.stringify([...debug.mock.calls, ...log.mock.calls])).not.toMatch(/private-token|ValidPassword123/);
  debug.mockRestore();
  log.mockRestore();
});

test("login hands validated backend response to the central AuthProvider", async () => {
  const api = { login: jest.fn().mockResolvedValue({ access_token: "provider-token", token_type: "bearer" }) };
  const transport = {
    configureAuthTokenProvider: jest.fn(),
    setAccessToken: jest.fn().mockResolvedValue(undefined),
    removeAccessToken: jest.fn().mockResolvedValue(undefined),
  };
  const provider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  const screen = render(
    <ThemeProvider persistPreference={false}>
      <AuthProvider transport={transport} tokenProvider={provider}>
        <LoginScreen onBack={jest.fn()} onCreateAccount={jest.fn()} api={api} />
      </AuthProvider>
    </ThemeProvider>,
  );
  fillLogin(screen);
  fireEvent.press(screen.getByTestId("login-submit"));
  await waitFor(() => expect(screen.getByText("Login successful")).toBeTruthy());
  expect(transport.setAccessToken).toHaveBeenCalledWith("provider-token");
});

test("login loading state prevents duplicate submissions", async () => {
  let resolveLogin;
  const api = { login: jest.fn(() => new Promise((resolve) => { resolveLogin = resolve; })) };
  const screen = themed(<LoginScreen onBack={jest.fn()} onCreateAccount={jest.fn()} api={api} tokenSetter={jest.fn()} />);
  fillLogin(screen);

  fireEvent.press(screen.getByTestId("login-submit"));
  fireEvent.press(screen.getByTestId("login-submit"));
  expect(api.login).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("login-submit").props.accessibilityState).toEqual({ disabled: true, busy: true });

  await act(async () => resolveLogin({ access_token: "token", token_type: "bearer" }));
  await waitFor(() => expect(screen.getByText("Login successful")).toBeTruthy());
});

test.each([
  [new ApiError("Unauthorized", { status: 401 }), /email or password is incorrect/],
  [new ApiError("Inactive", { status: 403 }), /currently inactive/],
  [new ApiError("Offline", { code: "NETWORK_ERROR" }), /cannot reach the server/],
  [new ApiError("Server", { status: 500 }), /could not complete authentication/],
])("login presents safe normalized failures", async (error, expected) => {
  const screen = themed(<LoginScreen onBack={jest.fn()} onCreateAccount={jest.fn()} api={{ login: jest.fn().mockRejectedValue(error) }} tokenSetter={jest.fn()} />);
  fillLogin(screen);
  fireEvent.press(screen.getByTestId("login-submit"));
  await waitFor(() => expect(screen.getByText(expected)).toBeTruthy());
});

test("signup submits the exact backend payload and shows pending verification", async () => {
  const api = {
    register: jest.fn().mockResolvedValue({
      id: "user-id",
      full_name: "Farm Owner",
      email: "owner@example.com",
      status: "ACTIVE",
      is_email_verified: false,
    }),
    resendVerification: jest.fn().mockResolvedValue({ detail: "generic" }),
  };
  const onLogIn = jest.fn();
  const screen = themed(<SignupScreen onBack={jest.fn()} onLogIn={onLogIn} api={api} />);
  fillSignup(screen);
  fireEvent.press(screen.getByTestId("signup-submit"));

  await waitFor(() => expect(screen.getByText("Account created")).toBeTruthy());
  expect(api.register).toHaveBeenCalledWith(
    { full_name: "Farm Owner", email: "owner@example.com", password: "ValidPassword123!" },
    { signal: expect.any(Object) },
  );
  expect(screen.getByText(/Check owner@example.com/)).toBeTruthy();
  expect(screen.getByText(/does not sign you in or create a farm/)).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "Resend Verification Email" }));
  await waitFor(() => expect(api.resendVerification).toHaveBeenCalledWith("owner@example.com", { signal: expect.any(Object) }));
  fireEvent.press(screen.getByRole("button", { name: "Go to Log In" }));
  expect(onLogIn).toHaveBeenCalledTimes(1);
});

test("signup maps duplicate and FastAPI field errors", async () => {
  const conflict = themed(<SignupScreen onBack={jest.fn()} onLogIn={jest.fn()} api={{ register: jest.fn().mockRejectedValue(new ApiError("Conflict", { status: 409 })) }} />);
  fillSignup(conflict);
  fireEvent.press(conflict.getByTestId("signup-submit"));
  await waitFor(() => expect(conflict.getByText(/already exists/)).toBeTruthy());
  conflict.unmount();

  const validationError = new ApiError("Validation", { status: 422, fieldErrors: { email: ["Backend email error"] } });
  const invalid = themed(<SignupScreen onBack={jest.fn()} onLogIn={jest.fn()} api={{ register: jest.fn().mockRejectedValue(validationError) }} />);
  fillSignup(invalid);
  fireEvent.press(invalid.getByTestId("signup-submit"));
  await waitFor(() => expect(invalid.getByText("Backend email error")).toBeTruthy());
});
