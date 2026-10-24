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
import { feedApi } from "../src/api/feed";
import { breedingApi } from "../src/api/breeding";
import { healthApi } from "../src/api/health";
import { invitationsApi } from "../src/api/invitations";
import { milkApi } from "../src/api/milk";
import { marketplaceApi } from "../src/api/marketplace";
import { permissionsApi } from "../src/api/permissions";
import { staffApi } from "../src/api/staff";

beforeEach(() => jest.clearAllMocks());

test("auth services use the real public and protected contracts", () => {
  authApi.register({ full_name: "Farm Owner", email: "owner@example.com", password: "password" });
  expect(apiClient.post).toHaveBeenCalledWith(
    "/auth/register",
    expect.objectContaining({
      auth: false,
      json: { full_name: "Farm Owner", email: "owner@example.com", password: "password" },
    }),
  );

  authApi.login({ email: "user@example.com", password: "password" });
  expect(apiClient.post).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ auth: false }));

  authApi.getCurrentUser();
  expect(apiClient.get).toHaveBeenCalledWith("/auth/me", undefined);

  authApi.verifyEmail("one-time-token");
  authApi.resendVerification("owner@example.com");
  authApi.forgotPassword("owner@example.com");
  authApi.resetPassword("reset-token", "NewPassword123!");
  expect(apiClient.post).toHaveBeenCalledWith("/auth/verify-email", expect.objectContaining({ auth: false, json: { token: "one-time-token" } }));
  expect(apiClient.post).toHaveBeenCalledWith("/auth/verification/resend", expect.objectContaining({ auth: false, json: { email: "owner@example.com" } }));
  expect(apiClient.post).toHaveBeenCalledWith("/auth/forgot-password", expect.objectContaining({ auth: false, json: { email: "owner@example.com" } }));
  expect(apiClient.post).toHaveBeenCalledWith("/auth/reset-password", expect.objectContaining({ auth: false, json: { token: "reset-token", new_password: "NewPassword123!" } }));
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

test("staff and invitation mutations use the reviewed methods, paths, and payloads", () => {
  const options = { signal: new AbortController().signal };
  invitationsApi.revoke("farm-id", "invite-id", options);
  invitationsApi.reissue("farm-id", "invite-id", options);
  staffApi.updateRole("farm-id", "member-id", "VETERINARIAN", options);
  staffApi.updateStatus("farm-id", "member-id", "INACTIVE", options);

  expect(apiClient.post).toHaveBeenNthCalledWith(
    1,
    "/farms/farm-id/invitations/invite-id/revoke",
    options,
  );
  expect(apiClient.post).toHaveBeenNthCalledWith(
    2,
    "/farms/farm-id/invitations/invite-id/reissue",
    options,
  );
  expect(apiClient.patch).toHaveBeenNthCalledWith(
    1,
    "/farms/farm-id/staff/member-id/role",
    { ...options, json: { role: "VETERINARIAN" } },
  );
  expect(apiClient.patch).toHaveBeenNthCalledWith(
    2,
    "/farms/farm-id/staff/member-id/status",
    { ...options, json: { status: "INACTIVE" } },
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

test("feed services use farm-scoped inventory and audited transaction routes", () => {
  const payload = { client_request_id: "11111111-1111-4111-8111-111111111111", quantity: "25" };
  feedApi.listItems("farm-id", { active_only: true });
  feedApi.createPurchase("farm-id", payload);
  feedApi.createConsumption("farm-id", payload);
  feedApi.updateNutritionPlan("farm-id", "plan-id", { status: "REVIEWED" });

  expect(apiClient.get).toHaveBeenCalledWith(
    "/farms/farm-id/feed/items",
    { query: { active_only: true } },
  );
  expect(apiClient.post).toHaveBeenCalledWith(
    "/farms/farm-id/feed/stock/purchases",
    { json: payload },
  );
  expect(apiClient.post).toHaveBeenCalledWith(
    "/farms/farm-id/feed/consumption",
    { json: payload },
  );
  expect(apiClient.patch).toHaveBeenCalledWith(
    "/farms/farm-id/feed/nutrition-plans/plan-id",
    { json: { status: "REVIEWED" } },
  );
});

test("breeding services use farm-scoped clinical and offspring routes", () => {
  const payload = { client_request_id: "11111111-1111-4111-8111-111111111111" };
  breedingApi.createHeat("farm-id", payload);
  breedingApi.createExam("farm-id", payload);
  breedingApi.registerOffspring("farm-id", "calving-id", payload);
  breedingApi.pedigree("farm-id", "cow-id", { generations: 4 });
  expect(apiClient.post).toHaveBeenNthCalledWith(1, "/farms/farm-id/breeding/heat-observations", { json: payload });
  expect(apiClient.post).toHaveBeenNthCalledWith(2, "/farms/farm-id/breeding/pregnancy-examinations", { json: payload });
  expect(apiClient.post).toHaveBeenNthCalledWith(3, "/farms/farm-id/breeding/calvings/calving-id/offspring", { json: payload });
  expect(apiClient.get).toHaveBeenCalledWith("/farms/farm-id/breeding/pedigree/cow-id", { query: { generations: 4 } });
});

test("marketplace services separate buyer and farm-scoped seller routes", () => {
  const bytes=new Uint8Array([1,2,3]);
  marketplaceApi.browse({search:"Sahiwal"});
  marketplaceApi.createInquiry("listing-id",{message:"May I inspect this animal?"});
  marketplaceApi.createListing("farm-id",{cattle_id:"cow-id"});
  marketplaceApi.uploadPhoto("farm-id","listing-id",{filename:"cow.png",bytes,contentType:"image/png",isPrimary:true});
  marketplaceApi.completeSale("farm-id","listing-id",{client_request_id:"request-id"});
  expect(apiClient.get).toHaveBeenCalledWith("/marketplace/listings",{query:{search:"Sahiwal"}});
  expect(apiClient.post).toHaveBeenCalledWith("/marketplace/listings/listing-id/inquiries",{json:{message:"May I inspect this animal?"}});
  expect(apiClient.post).toHaveBeenCalledWith("/farms/farm-id/marketplace/listings",{json:{cattle_id:"cow-id"}});
  expect(apiClient.post).toHaveBeenCalledWith("/farms/farm-id/marketplace/listings/listing-id/photos",expect.objectContaining({body:bytes,headers:{"Content-Type":"image/png"},query:{filename:"cow.png",is_primary:true},timeoutMs:60000}));
  expect(apiClient.post).toHaveBeenCalledWith("/farms/farm-id/marketplace/listings/listing-id/sales",{json:{client_request_id:"request-id"}});
});
