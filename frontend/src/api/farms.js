import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const farmsApi = Object.freeze({
  list: (options) => apiClient.get(apiRoutes.farms.collection, options),
  create: (payload, options) => apiClient.post(apiRoutes.farms.collection, { ...options, json: payload }),
  get: (farmId, options) => apiClient.get(apiRoutes.farms.detail(farmId), options),
  update: (farmId, payload, options) => apiClient.patch(apiRoutes.farms.detail(farmId), { ...options, json: payload }),
});
