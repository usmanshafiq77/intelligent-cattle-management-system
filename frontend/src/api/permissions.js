import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const permissionsApi = Object.freeze({
  getEffective: (farmId, options) => apiClient.get(apiRoutes.staff.myPermissions(farmId), options),
});
