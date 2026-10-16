import { Text } from "react-native";
import { render, waitFor } from "@testing-library/react-native";

jest.mock("expo-splash-screen", () => ({
  hideAsync: jest.fn().mockResolvedValue(undefined),
}));

import { StartupGate } from "../src/navigation/StartupGate";
import { ThemeProvider } from "../src/theme/ThemeProvider";

function Wrapper({ ready, hideSplash }) {
  return (
    <ThemeProvider persistPreference={false}>
      <StartupGate ready={ready} hideSplash={hideSplash}>
        <Text>Application ready</Text>
      </StartupGate>
    </ThemeProvider>
  );
}

test("startup gate shows branded progress until resources are ready", () => {
  const screen = render(<Wrapper ready={false} hideSplash={jest.fn()} />);
  expect(screen.getByLabelText("Preparing ICMS")).toBeTruthy();
  expect(screen.queryByText("Application ready")).toBeNull();
});

test("startup gate dismisses native splash without delaying ready content", async () => {
  const hideSplash = jest.fn().mockResolvedValue(undefined);
  const screen = render(<Wrapper ready hideSplash={hideSplash} />);

  expect(screen.getByText("Application ready")).toBeTruthy();
  await waitFor(() => expect(hideSplash).toHaveBeenCalledTimes(1));
});

test("native splash dismissal failure never leaves the application loading", async () => {
  const hideSplash = jest.fn().mockRejectedValue(new Error("native module unavailable"));
  const screen = render(<Wrapper ready hideSplash={hideSplash} />);

  expect(screen.getByText("Application ready")).toBeTruthy();
  await waitFor(() => expect(hideSplash).toHaveBeenCalledTimes(1));
});
