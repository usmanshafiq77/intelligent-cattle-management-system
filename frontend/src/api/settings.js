import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const settingsApi = Object.freeze({
  getFarm: (farmId, options) => apiClient.get(apiRoutes.settings.farm(farmId), options),
  updateFarm: (farmId, payload, options) => apiClient.put(apiRoutes.settings.farm(farmId), { ...options, json: payload }),
});
