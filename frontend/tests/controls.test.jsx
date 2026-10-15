import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { AppButton } from "../src/components/ui/AppButton";
import { AppInput } from "../src/components/ui/AppInput";
import { ThemeProvider } from "../src/theme/ThemeProvider";

jest.mock("../src/theme/useAppReducedMotion", () => ({ useAppReducedMotion: () => true }));

async function renderThemed(component) {
  return render(<ThemeProvider persistPreference={false}>{component}</ThemeProvider>);
}

describe("AppButton", () => {
  test("does not invoke disabled or loading actions", async () => {
    const onPress = jest.fn();
    const screen = await renderThemed(
      <>
        <AppButton title="Disabled action" disabled onPress={onPress} />
        <AppButton title="Pending action" loading onPress={onPress} />
      </>,
    );

    fireEvent.press(screen.getByRole("button", { name: "Disabled action" }));
    fireEvent.press(screen.getByRole("button", { name: "Pending action, loading" }));
    expect(onPress).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Pending action, loading" }).props.accessibilityState.busy).toBe(true);
  });

  test("invokes enabled actions once", async () => {
    const onPress = jest.fn();
    const screen = await renderThemed(<AppButton title="Continue" onPress={onPress} />);

    fireEvent.press(screen.getByRole("button", { name: "Continue" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});

describe("AppInput", () => {
  test("toggles password visibility with an accessible button", async () => {
    const screen = await renderThemed(
      <AppInput testID="password" label="Password" value="correct-horse" onChangeText={() => {}} secureTextEntry />,
    );

    expect(screen.getByTestId("password").props.secureTextEntry).toBe(true);
    await act(async () => {
      fireEvent.press(screen.getByRole("button", { name: "Show password" }));
    });
    expect(screen.getByTestId("password").props.secureTextEntry).toBe(false);
    expect(screen.getByRole("button", { name: "Hide password" })).toBeTruthy();
  });

  test("announces validation errors and exposes invalid state", async () => {
    const screen = await renderThemed(
      <AppInput testID="email" label="Email" value="invalid" onChangeText={() => {}} error="Enter a valid email address." />,
    );

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByText("Enter a valid email address.")).toBeTruthy();
    expect(screen.getByTestId("email").props["aria-invalid"]).toBe(true);
  });
});
