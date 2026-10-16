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
  expect(apiRoutes.staff.myPermissions("farm-id")).toBe("/farms/farm-id/staff/permissions/me");
  expect(apiRoutes.invitations.detail("farm-id", "invite-id")).toBe("/farms/farm-id/invitations/invite-id");
  expect(apiRoutes.cattle.detail("farm/id", "cow id")).toBe("/farms/farm%2Fid/cattle/cow%20id");
  expect(apiRoutes.healthRecords.history("farm-id", "cow-id")).toBe("/farms/farm-id/health/cattle/cow-id/history");
  expect(apiRoutes.milk.root("farm-id", "analytics")).toBe("/farms/farm-id/milk/analytics");
});
