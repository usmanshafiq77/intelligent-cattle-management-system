import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { ForgotPasswordScreen } from "../src/features/auth/screens/ForgotPasswordScreen";
import { ResetPasswordScreen } from "../src/features/auth/screens/ResetPasswordScreen";
import { ThemeProvider } from "../src/theme/ThemeProvider";

jest.setTimeout(15000);

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

test("forgot password validates, normalizes, and shows the generic result", async () => {
  const api = { forgotPassword: jest.fn().mockResolvedValue({ detail: "generic" }) };
  const onLogIn = jest.fn();
  const screen = themed(<ForgotPasswordScreen onBack={jest.fn()} onLogIn={onLogIn} api={api} />);

  fireEvent.changeText(screen.getByTestId("forgot-password-email"), "not-an-email");
  fireEvent.press(screen.getByTestId("forgot-password-submit"));
  expect(screen.getByText("Enter a valid email address.")).toBeTruthy();

  fireEvent.changeText(screen.getByTestId("forgot-password-email"), " Farmer@Example.COM ");
  fireEvent.press(screen.getByTestId("forgot-password-submit"));
  await waitFor(() => expect(screen.getByText("Check your email")).toBeTruthy());
  expect(api.forgotPassword).toHaveBeenCalledWith("farmer@example.com", { signal: expect.any(Object) });
  expect(screen.getByText(/same confirmation for every email address/i)).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "Back to Log In" }));
  expect(onLogIn).toHaveBeenCalledTimes(1);
});

test("reset password validates matching policy fields and submits the deep-link token", async () => {
  const api = { resetPassword: jest.fn().mockResolvedValue({ detail: "reset" }) };
  const onLogIn = jest.fn();
  const screen = themed(<ResetPasswordScreen token="one-time-token-value-that-is-long-enough" onBack={jest.fn()} onLogIn={onLogIn} api={api} />);

  fireEvent.changeText(screen.getByTestId("reset-password-new"), "short");
  fireEvent.changeText(screen.getByTestId("reset-password-confirm"), "different");
  fireEvent.press(screen.getByTestId("reset-password-submit"));
  expect(screen.getByText(/at least 8 characters/)).toBeTruthy();
  expect(screen.getByText("Passwords do not match.")).toBeTruthy();

  fireEvent.changeText(screen.getByTestId("reset-password-new"), "NewPassword123!");
  fireEvent.changeText(screen.getByTestId("reset-password-confirm"), "NewPassword123!");
  fireEvent.press(screen.getByTestId("reset-password-submit"));
  await waitFor(() => expect(screen.getByText("Password reset")).toBeTruthy());
  expect(api.resetPassword).toHaveBeenCalledWith(
    "one-time-token-value-that-is-long-enough",
    "NewPassword123!",
    { signal: expect.any(Object) },
  );
  fireEvent.press(screen.getByRole("button", { name: "Go to Log In" }));
  expect(onLogIn).toHaveBeenCalledTimes(1);
});

test("reset password presents invalid or missing link states safely", async () => {
  const missing = themed(<ResetPasswordScreen token="" onBack={jest.fn()} onLogIn={jest.fn()} onRequestNewLink={jest.fn()} api={{}} />);
  expect(missing.getByText(/missing its secure token/i)).toBeTruthy();
  expect(missing.getByTestId("reset-password-submit").props.accessibilityState.disabled).toBe(true);
  missing.unmount();

  const api = { resetPassword: jest.fn().mockRejectedValue(new ApiError("invalid", { status: 400 })) };
  const invalid = themed(<ResetPasswordScreen token="invalid-token-value-that-is-long-enough" onBack={jest.fn()} onLogIn={jest.fn()} api={api} />);
  fireEvent.changeText(invalid.getByTestId("reset-password-new"), "NewPassword123!");
  fireEvent.changeText(invalid.getByTestId("reset-password-confirm"), "NewPassword123!");
  fireEvent.press(invalid.getByTestId("reset-password-submit"));
  await waitFor(() => expect(invalid.getByText(/invalid, expired, revoked, or has already been used/i)).toBeTruthy());
});
