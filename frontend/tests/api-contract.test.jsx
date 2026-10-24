import fs from "node:fs";
import path from "node:path";

import {
  BACKEND_OPENAPI_OPERATION_COUNT,
  BACKEND_OPENAPI_PATH_COUNT,
  BACKEND_OPENAPI_SHA256,
  SUPPORTS_REFRESH_TOKENS,
} from "../src/api/backendContract";
import { apiRoutes } from "../src/api/routes";

test("frontend contract checkpoint matches the backend OpenAPI guard", () => {
  const backendGuard = fs.readFileSync(
    path.resolve(__dirname, "../../backend/tests/test_openapi_contract.py"),
    "utf8",
  );
  expect(backendGuard).toContain(BACKEND_OPENAPI_SHA256);
  expect(backendGuard).toContain(`assert len(specification["paths"]) == ${BACKEND_OPENAPI_PATH_COUNT}`);
  expect(backendGuard).toContain(`assert operation_count == ${BACKEND_OPENAPI_OPERATION_COUNT}`);
  expect(SUPPORTS_REFRESH_TOKENS).toBe(false);
});

test("critical service routes match the reviewed FastAPI paths", () => {
  expect(apiRoutes.auth.login).toBe("/auth/login");
  expect(apiRoutes.auth.me).toBe("/auth/me");
  expect(apiRoutes.auth.forgotPassword).toBe("/auth/forgot-password");
  expect(apiRoutes.auth.resetPassword).toBe("/auth/reset-password");
  expect(apiRoutes.staff.myPermissions("farm-id")).toBe("/farms/farm-id/staff/permissions/me");
  expect(apiRoutes.invitations.detail("farm-id", "invite-id")).toBe("/farms/farm-id/invitations/invite-id");
  expect(apiRoutes.cattle.detail("farm/id", "cow id")).toBe("/farms/farm%2Fid/cattle/cow%20id");
  expect(apiRoutes.cattle.summary("farm-id")).toBe("/farms/farm-id/cattle/summary");
  expect(apiRoutes.healthRecords.history("farm-id", "cow-id")).toBe("/farms/farm-id/health/cattle/cow-id/history");
  expect(apiRoutes.milk.root("farm-id", "analytics")).toBe("/farms/farm-id/milk/analytics");
  expect(apiRoutes.feed.root("farm-id", "items")).toBe("/farms/farm-id/feed/items");
  expect(apiRoutes.feed.item("farm/id", "feed id")).toBe("/farms/farm%2Fid/feed/items/feed%20id");
  expect(apiRoutes.feed.nutritionPlan("farm-id", "plan-id")).toBe("/farms/farm-id/feed/nutrition-plans/plan-id");
});

test("auth form contract remains aligned with the backend schemas and JSON routes", () => {
  const userSchema = fs.readFileSync(
    path.resolve(__dirname, "../../backend/app/schemas/user.py"),
    "utf8",
  );
  const authRouter = fs.readFileSync(
    path.resolve(__dirname, "../../backend/app/api/v1/auth.py"),
    "utf8",
  );

  expect(userSchema).toMatch(/class UserRegister[\s\S]*full_name:[\s\S]*min_length=2, max_length=150/);
  expect(userSchema).toMatch(/class UserRegister[\s\S]*email: EmailStr[\s\S]*max_length=254/);
  expect(userSchema).toMatch(/class UserRegister[\s\S]*password:[\s\S]*min_length=8, max_length=128/);
  expect(userSchema).toMatch(/class UserLogin[\s\S]*password:[\s\S]*min_length=1, max_length=128/);
  expect(userSchema).toMatch(/class TokenResponse[\s\S]*access_token: str[\s\S]*token_type: str/);
  expect(authRouter).toMatch(/"\/register"[\s\S]*response_model=RegistrationResponse[\s\S]*status_code=status\.HTTP_201_CREATED/);
  expect(authRouter).toMatch(/"\/login"[\s\S]*response_model=TokenResponse/);
});
