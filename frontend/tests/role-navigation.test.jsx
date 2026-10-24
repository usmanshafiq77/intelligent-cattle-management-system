import { fireEvent, render } from "@testing-library/react-native";

import { ThemeProvider } from "../src/theme/ThemeProvider";
import { RoleNavigation } from "../src/features/navigation/components/RoleNavigation";
import { requireEffectivePermissions } from "../src/features/farms/farmContracts";
import { farmNavigationItems, moduleForRoute, platformNavigationItems } from "../src/features/permissions/navigationConfig";

function itemsFor(permissions) {
  const allowed = new Set(permissions);
  return farmNavigationItems((permission) => allowed.has(permission));
}

test.each([
  ["FARM_OWNER", ["farm.view", "staff.view", "cattle.view", "health.view", "milk.view"], ["farm", "staff", "cattle", "health", "milk"]],
  ["WORKER", ["farm.view", "cattle.view", "health.view", "milk.view"], ["farm", "cattle", "health", "milk"]],
  ["VETERINARIAN", ["farm.view", "cattle.view", "health.view", "milk.view"], ["farm", "cattle", "health", "milk"]],
])("%s menu exposes only backend-granted modules", (_role, permissions, expected) => {
  expect(itemsFor(permissions).map((item) => item.key)).toEqual(expected);
});

test("missing and unknown permissions default to denied", () => {
  expect(itemsFor([])).toEqual([]);
  expect(itemsFor(["unknown.permission"])).toEqual([]);
  expect(farmNavigationItems()).toEqual([]);
});

test("system administrator navigation is based only on verified auth/me state", () => {
  const items = platformNavigationItems({ is_system_admin: true });
  expect(items.map((item) => item.key)).toEqual(["platform-backups", "marketplace-moderation", "breed-catalog"]);
  expect(items[0]).toEqual(expect.objectContaining({ href: "/admin/backups", comingSoon: false }));
  expect(platformNavigationItems({ is_system_admin: false })).toEqual([]);
  expect(platformNavigationItems(null)).toEqual([]);
});

test("effective permission contract rejects cross-farm data", () => {
  const response = { farm_id: "farm-b", membership_id: "member", predefined_role: "WORKER", custom_role_ids: [], permissions: ["farm.view"] };
  expect(() => requireEffectivePermissions(response, "farm-a")).toThrow("effective-permissions");
});

test("direct module routes resolve only centralized known destinations", () => {
  expect(moduleForRoute("health")).toMatchObject({ permission: "health.view" });
  expect(moduleForRoute("finance")).toMatchObject({ permission: "finance.view" });
  expect(moduleForRoute(["health"])).toBeNull();
});

test.each([
  [true, "desktop-navigation"],
  [false, "mobile-navigation"],
])("navigation renders an accessible %s layout", (desktop, testID) => {
  const onNavigate = jest.fn();
  const screen = render(
    <ThemeProvider persistPreference={false}>
      <RoleNavigation items={itemsFor(["health.view"])} desktop={desktop} onNavigate={onNavigate} />
    </ThemeProvider>,
  );
  expect(screen.getByTestId(testID)).toBeTruthy();
  fireEvent.press(screen.getByLabelText("Health"));
  expect(onNavigate).toHaveBeenCalledWith("/health");
  fireEvent.press(screen.getByLabelText("Profile"));
  expect(onNavigate).toHaveBeenCalledWith("/profile");
});
