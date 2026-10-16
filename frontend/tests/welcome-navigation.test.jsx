import { Animated, Text } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";

const mockPush = jest.fn();

jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), back: jest.fn(), canGoBack: () => true }),
}));

jest.mock("../src/theme/useAppReducedMotion", () => ({
  useAppReducedMotion: () => true,
}));

import { WelcomeScreen } from "../src/features/onboarding/screens/WelcomeScreen";
import { DevelopmentOnlyRoute, isDevelopmentRouteEnabled } from "../src/navigation/DevelopmentOnlyRoute";
import { ROUTES } from "../src/navigation/routes";
import { ThemeProvider } from "../src/theme/ThemeProvider";

function themed(node) {
  return render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);
}

beforeEach(() => jest.clearAllMocks());

test("the startup welcome screen renders the real ICMS entry content", () => {
  const screen = themed(<WelcomeScreen />);

  expect(screen.getByRole("header", { name: /Smarter Farming/ })).toBeTruthy();
  expect(screen.getByText(/Manage your cattle, monitor farm activities/)).toBeTruthy();
  expect(screen.getByLabelText(/Connected farm overview/)).toBeTruthy();
});

test("Get Started and Log In navigate to the authentication routes", () => {
  const screen = themed(<WelcomeScreen />);

  fireEvent.press(screen.getByRole("button", { name: "Get Started" }));
  fireEvent.press(screen.getByRole("button", { name: "Log In" }));

  expect(mockPush).toHaveBeenNthCalledWith(1, ROUTES.signup);
  expect(mockPush).toHaveBeenNthCalledWith(2, ROUTES.login);
});

test("development showcase is rendered only when the development guard is enabled", () => {
  expect(isDevelopmentRouteEnabled(true)).toBe(true);
  expect(isDevelopmentRouteEnabled(false)).toBe(false);

  const enabled = themed(
    <DevelopmentOnlyRoute enabled><Text>Design showcase content</Text></DevelopmentOnlyRoute>,
  );
  expect(enabled.getByText("Design showcase content")).toBeTruthy();
  enabled.unmount();

  const disabled = themed(
    <DevelopmentOnlyRoute enabled={false} onReturnHome={jest.fn()}>
      <Text>Design showcase content</Text>
    </DevelopmentOnlyRoute>,
  );
  expect(disabled.queryByText("Design showcase content")).toBeNull();
  expect(disabled.getByRole("header", { name: "Page not found" })).toBeTruthy();
});

test("welcome entrance respects the reduced-motion preference", () => {
  const timing = jest.spyOn(Animated, "timing");
  themed(<WelcomeScreen />);
  expect(timing).not.toHaveBeenCalled();
});
