jest.mock("expo-router", () => ({
  useRouter: () => ({ push: jest.fn() }),
  useLocalSearchParams: () => ({}),
}));

import { apiRoutes } from "../src/api/routes";
import { authApi } from "../src/api/auth";
import { settingsApi } from "../src/api/settings";
import { backupsApi } from "../src/api/backups";
import * as settingsScreens from "../src/features/settings/screens/SettingsScreens";
import * as backupScreens from "../src/features/backups/screens/BackupScreens";
import { platformNavigationItems } from "../src/features/permissions/navigationConfig";

test("settings API uses authenticated user and farm-scoped contracts", () => {
  expect(apiRoutes.auth.preferences).toBe("/auth/me/preferences");
  expect(apiRoutes.settings.farm("farm one")).toBe("/farms/farm%20one/settings");
  expect(typeof authApi.changePassword).toBe("function");
  expect(typeof authApi.requestEmailChange).toBe("function");
  expect(typeof settingsApi.updateFarm).toBe("function");
});

test("backup API exposes queue, verification, isolated restore and OAuth contracts", () => {
  expect(apiRoutes.backups.jobs).toBe("/admin/backups/jobs");
  expect(apiRoutes.backups.restoreTest("job/id")).toBe("/admin/backups/jobs/job%2Fid/restore-test");
  expect(typeof backupsApi.request).toBe("function");
  expect(typeof backupsApi.verify).toBe("function");
  expect(typeof backupsApi.googleFiles).toBe("function");
});

test("required settings and backup screens are real exported components", () => {
  ["SettingsHomeScreen", "PersonalSettingsScreen", "SecuritySettingsScreen", "AppearanceSettingsScreen", "FarmSettingsScreen", "AccountManagementScreen"].forEach((name) => expect(typeof settingsScreens[name]).toBe("function"));
  ["BackupDashboardScreen", "BackupSectionScreen", "BackupDetailScreen"].forEach((name) => expect(typeof backupScreens[name]).toBe("function"));
});

test("platform backup navigation is restricted to verified system-admin state", () => {
  expect(platformNavigationItems({ is_system_admin: false }).some((x) => x.key === "platform-backups")).toBe(false);
  expect(platformNavigationItems({ is_system_admin: true })).toEqual(expect.arrayContaining([expect.objectContaining({ key: "platform-backups", href: "/admin/backups", comingSoon: false })]));
});
