import { render } from "@testing-library/react-native";
import { Text } from "react-native";

import { RequireFarm, RequirePermission, useActiveFarm, useCan } from "../src/features/permissions/guards";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarmState;
jest.mock("../src/features/farms/context/FarmProvider", () => ({
  useFarm: () => mockFarmState,
}));

function HookProbe() {
  const farm = useActiveFarm();
  const allowed = useCan("health.view");
  return <Text testID="hook-result">{`${farm?.id || "none"}:${allowed}`}</Text>;
}

function renderGuard(content) {
  return render(<ThemeProvider persistPreference={false}>{content}</ThemeProvider>);
}

beforeEach(() => {
  mockFarmState = {
    status: "ready",
    activeFarm: { id: "farm-a", name: "North Farm" },
    isLoading: false,
    issue: null,
    can: jest.fn((permission) => permission === "health.view"),
    refreshFarms: jest.fn(),
  };
});

test("allowed permission renders protected content and hooks expose verified scope", () => {
  const screen = renderGuard(
    <RequirePermission permission="health.view"><Text>Protected health content</Text><HookProbe /></RequirePermission>,
  );
  expect(screen.getByText("Protected health content")).toBeTruthy();
  expect(screen.getByTestId("hook-result").props.children).toBe("farm-a:true");
});

test("missing and malformed permissions fail closed", () => {
  const missing = renderGuard(<RequirePermission permission="staff.manage"><Text>Sensitive staff content</Text></RequirePermission>);
  expect(missing.queryByText("Sensitive staff content")).toBeNull();
  expect(missing.getByText("Access denied")).toBeTruthy();
  missing.unmount();

  const malformed = renderGuard(<RequirePermission permission={null}><Text>Sensitive content</Text></RequirePermission>);
  expect(malformed.queryByText("Sensitive content")).toBeNull();
  expect(malformed.getByText("Access denied")).toBeTruthy();
});

test.each([
  ["loading", true, "Verifying farm access"],
  ["selection-required", false, "Choose a farm"],
  ["no-farms", false, "No accessible farms"],
])("farm guard blocks protected content during %s", (status, isLoading, expected) => {
  mockFarmState = { ...mockFarmState, status, activeFarm: null, isLoading };
  const screen = renderGuard(<RequireFarm><Text>Farm secret</Text></RequireFarm>);
  expect(screen.queryByText("Farm secret")).toBeNull();
  expect(screen.getByText(expected)).toBeTruthy();
});

test("permission API unavailable never leaves old protected content visible", () => {
  mockFarmState = {
    ...mockFarmState,
    status: "permission-unavailable",
    activeFarm: null,
    isLoading: false,
    issue: { message: "Farm access could not be verified safely." },
  };
  const screen = renderGuard(<RequirePermission permission="health.view"><Text>Old farm health</Text></RequirePermission>);
  expect(screen.queryByText("Old farm health")).toBeNull();
  expect(screen.getByText("Farm access unavailable")).toBeTruthy();
});
