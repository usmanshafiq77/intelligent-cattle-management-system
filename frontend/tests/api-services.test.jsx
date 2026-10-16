jest.mock("../src/api/client", () => ({
  DEFAULT_UPLOAD_TIMEOUT_MS: 60000,
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

import { apiClient } from "../src/api/client";
import { authApi } from "../src/api/auth";
import { cattleApi } from "../src/api/cattle";
import { farmsApi } from "../src/api/farms";
import { healthApi } from "../src/api/health";
import { invitationsApi } from "../src/api/invitations";
import { milkApi } from "../src/api/milk";
import { permissionsApi } from "../src/api/permissions";
import { staffApi } from "../src/api/staff";

beforeEach(() => jest.clearAllMocks());

test("auth services use the real public and protected contracts", () => {
  authApi.login({ email: "user@example.com", password: "password" });
  expect(apiClient.post).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ auth: false }));

  authApi.getCurrentUser();
  expect(apiClient.get).toHaveBeenCalledWith("/auth/me", undefined);
});

test("farm, staff, and permission services use farm-scoped routes", () => {
  farmsApi.list();
  staffApi.list("farm-id", { limit: 20 });
  permissionsApi.getEffective("farm-id");

  expect(apiClient.get).toHaveBeenNthCalledWith(1, "/farms", undefined);
  expect(apiClient.get).toHaveBeenNthCalledWith(2, "/farms/farm-id/staff", { query: { limit: 20 } });
  expect(apiClient.get).toHaveBeenNthCalledWith(3, "/farms/farm-id/staff/permissions/me", undefined);
});

test("invitation acceptance remains authenticated and uses the real token payload", () => {
  invitationsApi.accept("invitation-token");
  expect(apiClient.post).toHaveBeenCalledWith(
    "/invitations/accept",
    { json: { token: "invitation-token" } },
  );
});

test("cattle media upload matches the backend raw-body contract", () => {
  const content = new Uint8Array([1, 2, 3]);
  cattleApi.uploadMedia("farm", "cow", content, {
    filename: "cow.png",
    purpose: "PROFILE",
    contentType: "image/png",
  });

  expect(apiClient.post).toHaveBeenCalledWith(
    "/farms/farm/cattle/cow/media",
    expect.objectContaining({
      body: content,
      query: { filename: "cow.png", purpose: "PROFILE" },
      headers: { "Content-Type": "image/png" },
      timeoutMs: 60000,
    }),
  );
});

test("health and milk actions match reviewed transition endpoints", () => {
  healthApi.finalizeEncounter("farm", "encounter", { notes: "complete" });
  milkApi.getActiveLactation("farm", "cow");

  expect(apiClient.post).toHaveBeenCalledWith(
    "/farms/farm/health/encounters/encounter/finalize",
    { json: { notes: "complete" } },
  );
  expect(apiClient.get).toHaveBeenCalledWith(
    "/farms/farm/milk/lactations/active",
    { query: { cattle_id: "cow" } },
  );
});
