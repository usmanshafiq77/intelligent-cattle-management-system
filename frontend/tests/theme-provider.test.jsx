import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import { ThemeProvider, THEME_STORAGE_KEY, useAppTheme } from "../src/theme/ThemeProvider";

function ThemeProbe() {
  const { themeId, isThemeReady, themeRestoreError, changeTheme } = useAppTheme();
  return (
    <>
      <Text>{isThemeReady ? `ready:${themeId}` : "restoring"}</Text>
      {themeRestoreError ? <Text>restore-error</Text> : null}
      <Pressable accessibilityRole="button" accessibilityLabel="Use midnight theme" onPress={() => changeTheme("midnight").catch(() => {})}>
        <Text>Change theme</Text>
      </Pressable>
    </>
  );
}

describe("ThemeProvider", () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    jest.clearAllMocks();
  });

  test("restores a valid persisted theme before declaring readiness", async () => {
    let resolveStoredTheme;
    AsyncStorage.getItem.mockReturnValueOnce(new Promise((resolve) => { resolveStoredTheme = resolve; }));
    const screen = render(<ThemeProvider><ThemeProbe /></ThemeProvider>);

    expect(screen.getByText("restoring")).toBeTruthy();
    await act(async () => {
      resolveStoredTheme("indigo");
    });

    await waitFor(() => expect(screen.getByText("ready:indigo")).toBeTruthy());
    expect(AsyncStorage.getItem).toHaveBeenCalledWith(THEME_STORAGE_KEY);
  });

  test("switches reactively and persists the selected theme", async () => {
    let resolveStoredTheme;
    AsyncStorage.getItem.mockReturnValueOnce(new Promise((resolve) => { resolveStoredTheme = resolve; }));
    const screen = render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    await act(async () => {
      resolveStoredTheme(null);
    });
    await waitFor(() => expect(screen.getByText("ready:emerald")).toBeTruthy());

    await act(async () => {
      fireEvent.press(screen.getByRole("button", { name: "Use midnight theme" }));
    });

    await waitFor(() => expect(screen.getByText("ready:midnight")).toBeTruthy());
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(THEME_STORAGE_KEY, "midnight");
  });

  test("rolls back the visible theme when persistence fails", async () => {
    let resolveStoredTheme;
    AsyncStorage.getItem.mockReturnValueOnce(new Promise((resolve) => { resolveStoredTheme = resolve; }));
    AsyncStorage.setItem.mockRejectedValueOnce(new Error("storage unavailable"));
    const screen = render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    await act(async () => {
      resolveStoredTheme(null);
    });
    await waitFor(() => expect(screen.getByText("ready:emerald")).toBeTruthy());

    await act(async () => {
      fireEvent.press(screen.getByRole("button", { name: "Use midnight theme" }));
    });

    await waitFor(() => expect(screen.getByText("ready:emerald")).toBeTruthy());
  });

  test("continues with the default theme when initial restoration fails", async () => {
    AsyncStorage.getItem.mockRejectedValueOnce(new Error("storage unavailable"));
    const screen = render(<ThemeProvider><ThemeProbe /></ThemeProvider>);

    await waitFor(() => expect(screen.getByText("ready:emerald")).toBeTruthy());
    expect(screen.getByText("restore-error")).toBeTruthy();
  });
});
