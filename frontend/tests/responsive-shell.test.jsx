import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { BackHandler, StyleSheet } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { Screen } from "../src/components/ui/Screen";
import { AdaptiveNavigationProvider } from "../src/features/navigation/components/AdaptiveNavigation";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockPathname = "/health";
const mockPush = jest.fn();
let mockFarm;
const mockAuth = { status: "authenticated", user: { full_name: "Mobile User", email: "mobile@example.com", is_system_admin: false }, logout: jest.fn().mockResolvedValue(undefined) };

jest.mock("expo-router", () => ({ usePathname: () => mockPathname, useRouter: () => ({ push: mockPush }) }));
jest.mock("../src/features/auth/context/AuthProvider", () => ({ useAuth: () => mockAuth }));
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

function renderShell({ width = 360, height = 800, top = 32, bottom = 18, fontScale = 1 } = {}) {
  jest.spyOn(require("react-native"), "useWindowDimensions").mockReturnValue({ width, height, scale: 1, fontScale });
  const metrics = { frame: { x: 0, y: 0, width, height }, insets: { top, bottom, left: 0, right: 0 } };
  return render(<SafeAreaProvider initialMetrics={metrics}><ThemeProvider persistPreference={false}><AdaptiveNavigationProvider><Screen><></></Screen></AdaptiveNavigationProvider></ThemeProvider></SafeAreaProvider>);
}

beforeEach(() => {
  jest.restoreAllMocks(); mockPush.mockClear(); mockPathname = "/health";
  mockAuth.user = { full_name: "Mobile User", email: "mobile@example.com", is_system_admin: false };
  mockFarm = { activeFarm: { id: "farm-a", name: "Green Valley" }, farms: [{ id: "farm-a", name: "Green Valley" }], membership: { role: "WORKER" }, permissions: ["farm.view", "cattle.view", "health.view"], isLoading: false, can: jest.fn((permission) => ["farm.view", "cattle.view", "health.view"].includes(permission)), selectFarm: jest.fn().mockResolvedValue({ selected: true }) };
});

function enableAllFarmModules() {
  mockFarm = { ...mockFarm, membership: { role: "FARM_OWNER" }, can: jest.fn(() => true) };
}

test("phone header honors nonzero safe-area insets and exposes a 48-point hamburger", () => {
  const screen = renderShell({ width: 320, top: 36, bottom: 20 });
  const header = screen.getByTestId("safe-area-header");
  expect(StyleSheet.flatten(header.props.style).paddingTop).toBe(36);
  const button = screen.getByTestId("hamburger-button");
  expect(StyleSheet.flatten(button.props.style)).toEqual(expect.objectContaining({ width: 48, height: 48 }));
  expect(StyleSheet.flatten(screen.getByTestId("app-shell-content").props.style).paddingBottom).toBe(20);
  expect(screen.queryByTestId("mobile-navigation")).toBeNull();
});

test("hamburger drawer closes from backdrop, close button, navigation, and Android Back", async () => {
  let backHandler;
  jest.spyOn(BackHandler, "addEventListener").mockImplementation((_event, handler) => { backHandler = handler; return { remove: jest.fn() }; });
  const screen = renderShell();
  fireEvent.press(screen.getByTestId("hamburger-button"));
  expect(screen.getByTestId("mobile-navigation-drawer")).toBeTruthy();
  fireEvent.press(screen.getByTestId("drawer-backdrop"));
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
  fireEvent.press(screen.getByTestId("hamburger-button"));
  fireEvent.press(screen.getByTestId("drawer-close"));
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
  fireEvent.press(screen.getByTestId("hamburger-button"));
  await waitFor(() => expect(backHandler).toEqual(expect.any(Function)));
  let handled;
  act(() => { handled = backHandler(); });
  expect(handled).toBe(true);
  await waitFor(() => expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull());
  fireEvent.press(screen.getByTestId("hamburger-button"));
  fireEvent.press(screen.getByLabelText("Cattle"));
  expect(mockPush).toHaveBeenCalledWith("/cattle");
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
});

test("drawer highlights the current route and omits unauthorized finance links", () => {
  const screen = renderShell(); fireEvent.press(screen.getByTestId("hamburger-button"));
  expect(screen.getByLabelText("Health").props.accessibilityState.selected).toBe(true);
  expect(screen.queryByLabelText("Finance & Resources")).toBeNull();
  expect(screen.getByLabelText("Vaccinations")).toBeTruthy();
});

test("mobile drawer uses the dark profile-led visual hierarchy without changing menu semantics", () => {
  const screen = renderShell({ width: 390, height: 844, top: 32, bottom: 24 });
  fireEvent.press(screen.getByTestId("hamburger-button"));
  expect(screen.getByTestId("mobile-drawer-profile")).toBeTruthy();
  expect(screen.getByText("Mobile User")).toBeTruthy();
  expect(screen.getByText("mobile@example.com")).toBeTruthy();
  expect(screen.getAllByText("Green Valley").length).toBeGreaterThan(0);
  expect(StyleSheet.flatten(screen.getByTestId("mobile-navigation-drawer").props.style)).toEqual(expect.objectContaining({ backgroundColor: "#0A1219", borderTopRightRadius: 24, borderBottomRightRadius: 24 }));
  expect(StyleSheet.flatten(screen.getByTestId("navigation-drawer-content").props.style).backgroundColor).toBe("#0A1219");
  expect(StyleSheet.flatten(screen.getByTestId("drawer-close").props.style)).toEqual(expect.objectContaining({ width: 48, height: 48 }));
  expect(screen.getByLabelText("Health").props.accessibilityState.selected).toBe(true);
  expect(screen.getByLabelText("Dashboard").props.accessibilityState.selected).toBe(false);
});

test("profile and security is the second navigation destination and still closes the drawer", () => {
  const screen = renderShell();
  fireEvent.press(screen.getByTestId("hamburger-button"));
  const links = screen.getAllByRole("link");
  expect(links[0].props.accessibilityLabel).toBe("Dashboard");
  expect(links[1].props.accessibilityLabel).toBe("Profile & Security");
  expect(screen.getAllByLabelText("Profile & Security")).toHaveLength(1);
  fireEvent.press(screen.getByLabelText("Profile & Security"));
  expect(mockPush).toHaveBeenCalledWith("/profile");
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
});

test("short mobile drawer has one shrinkable scroll viewport and safe bottom content inset", () => {
  enableAllFarmModules();
  const screen = renderShell({ width: 320, height: 568, top: 36, bottom: 34, fontScale: 1.3 });
  fireEvent(screen.getByTestId("adaptive-app-shell"), "layout", { nativeEvent: { layout: { x: 0, y: 0, width: 320, height: 540 } } });
  fireEvent.press(screen.getByTestId("hamburger-button"));
  const overlay = screen.getByTestId("mobile-drawer-overlay");
  const drawer = screen.getByTestId("mobile-navigation-drawer");
  const content = screen.getByTestId("navigation-drawer-content");
  const scroll = screen.getByTestId("navigation-drawer-scroll");
  expect(StyleSheet.flatten(overlay.props.style)).toEqual(expect.objectContaining({ position: "absolute", top: 36, height: 470, overflow: "hidden" }));
  expect(StyleSheet.flatten(drawer.props.style)).toEqual(expect.objectContaining({ width: 300, height: 470, maxHeight: 470, minHeight: 0, overflow: "hidden", zIndex: 1 }));
  expect(StyleSheet.flatten(screen.getByTestId("mobile-drawer-profile").props.style).paddingTop).toBe(12);
  expect(StyleSheet.flatten(content.props.style)).toEqual(expect.objectContaining({ flex: 1, minHeight: 0 }));
  expect(StyleSheet.flatten(scroll.props.style)).toEqual(expect.objectContaining({ flex: 1, minHeight: 0 }));
  expect(StyleSheet.flatten(scroll.props.contentContainerStyle)).toEqual(expect.objectContaining({ flexGrow: 1, paddingBottom: 16 }));
  expect(scroll.props.nestedScrollEnabled).toBe(true);
  expect(scroll.props.contentInsetAdjustmentBehavior).toBe("never");
});

test("scrolling a short owner drawer reaches and activates the final authorized module", () => {
  enableAllFarmModules();
  mockAuth.user = { full_name: "Owner Admin", is_system_admin: true };
  const screen = renderShell({ width: 320, height: 568, top: 36, bottom: 34, fontScale: 1.3 });
  fireEvent.press(screen.getByTestId("hamburger-button"));
  const scroll = screen.getByTestId("navigation-drawer-scroll");
  expect(screen.getByLabelText("Dashboard")).toBeTruthy();
  expect(screen.getByLabelText("Profile & Security")).toBeTruthy();
  expect(screen.getByLabelText("Feed & Nutrition")).toBeTruthy();
  expect(screen.getByLabelText("Breeding & Genetics")).toBeTruthy();
  expect(screen.getByLabelText("Finance & Resources")).toBeTruthy();
  expect(screen.getByLabelText("Cattle Marketplace")).toBeTruthy();
  expect(screen.getByLabelText("Vaccinations")).toBeTruthy();
  expect(screen.getByLabelText("Marketplace Moderation")).toBeTruthy();
  fireEvent.scroll(scroll, { nativeEvent: { contentOffset: { y: 900 }, contentSize: { height: 1200, width: 300 }, layoutMeasurement: { height: 420, width: 300 } } });
  fireEvent.press(screen.getByLabelText("Marketplace Moderation"));
  expect(mockPush).toHaveBeenCalledWith("/marketplace/moderation");
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
});

test.each([
  [320, 568, 36, 34, 1.3],
  [360, 800, 32, 24, 1],
  [390, 844, 28, 20, 1.3],
  [412, 915, 24, 18, 1],
  [600, 960, 24, 24, 1],
  [768, 1024, 24, 20, 1],
  [768, 420, 20, 18, 1.3],
])("%i x %i drawer keeps its final authorized item in the scroll surface", (width, height, top, bottom, fontScale) => {
  enableAllFarmModules();
  const screen = renderShell({ width, height, top, bottom, fontScale });
  fireEvent.press(screen.getByTestId("hamburger-button"));
  expect(screen.getByTestId("navigation-drawer-scroll")).toBeTruthy();
  expect(screen.getByLabelText("Cattle Marketplace")).toBeTruthy();
  expect(screen.getByLabelText("Log out")).toBeTruthy();
  expect(StyleSheet.flatten(screen.getByTestId("mobile-drawer-overlay").props.style).top).toBe(top);
  expect(StyleSheet.flatten(screen.getByTestId("mobile-drawer-overlay").props.style).height).toBe(height - top - bottom);
  expect(StyleSheet.flatten(screen.getByTestId("mobile-navigation-drawer").props.style).maxHeight).toBe(height - top - bottom);
  expect(StyleSheet.flatten(screen.getByTestId("navigation-drawer-scroll").props.contentContainerStyle).paddingBottom).toBe(16);
});

test("desktop uses a persistent sidebar without a hamburger or mobile drawer", () => {
  const screen = renderShell({ width: 1366, top: 0, bottom: 0 });
  expect(screen.queryByTestId("hamburger-button")).toBeNull();
  expect(screen.getByTestId("navigation-drawer-scroll")).toBeTruthy();
  expect(StyleSheet.flatten(screen.getByTestId("navigation-drawer-content").props.style)).toEqual(expect.objectContaining({ flex: 0, width: 280, minHeight: 0 }));
  expect(screen.queryByTestId("mobile-drawer-profile")).toBeNull();
  expect(screen.queryByTestId("mobile-navigation-drawer")).toBeNull();
});

test.each([
  [320, 568, 1, "hamburger-button"],
  [360, 800, 1, "hamburger-button"],
  [390, 844, 1.3, "hamburger-button"],
  [412, 915, 1, "hamburger-button"],
  [600, 960, 1, "hamburger-button"],
  [768, 1024, 1, "hamburger-button"],
  [1024, 768, 1, "navigation-drawer-scroll"],
  [1366, 768, 1, "navigation-drawer-scroll"],
])("%i x %i with font scale %s selects the expected adaptive navigation", (width, height, fontScale, testID) => {
  const screen = renderShell({ width, height, fontScale, top: 24, bottom: 16 });
  expect(screen.getByTestId(testID)).toBeTruthy();
});
