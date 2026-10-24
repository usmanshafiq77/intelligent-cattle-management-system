import { apiClient } from "./client";
import { apiRoutes } from "./routes";

const root = apiRoutes.milk.root;
const detail = apiRoutes.milk.detail;

export const milkApi = Object.freeze({
  listLactations: (farmId, query, options) => apiClient.get(root(farmId, "lactations"), { ...options, query }),
  createLactation: (farmId, payload, options) => apiClient.post(root(farmId, "lactations"), { ...options, json: payload }),
  getActiveLactation: (farmId, cattleId, options) => apiClient.get(`${root(farmId, "lactations")}/active`, { ...options, query: { cattle_id: cattleId } }),
  getLactation: (farmId, lactationId, options) => apiClient.get(detail(farmId, "lactations", lactationId), options),
  transitionLactation: (farmId, lactationId, payload, options) => apiClient.post(`${detail(farmId, "lactations", lactationId)}/transition`, { ...options, json: payload }),
  listSessions: (farmId, query, options) => apiClient.get(root(farmId, "sessions"), { ...options, query }),
  createSession: (farmId, payload, options) => apiClient.post(root(farmId, "sessions"), { ...options, json: payload }),
  createSessionsBulk: (farmId, payload, options) => apiClient.post(`${root(farmId, "sessions")}/bulk`, { ...options, json: payload }),
  getSession: (farmId, sessionId, options) => apiClient.get(detail(farmId, "sessions", sessionId), options),
  listQualityTests: (farmId, query, options) => apiClient.get(root(farmId, "quality"), { ...options, query }),
  createQualityTest: (farmId, payload, options) => apiClient.post(root(farmId, "quality"), { ...options, json: payload }),
  getQualityTest: (farmId, qualityId, options) => apiClient.get(detail(farmId, "quality", qualityId), options),
  listCorrections: (farmId, query, options) => apiClient.get(root(farmId, "corrections"), { ...options, query }),
  createCorrection: (farmId, payload, options) => apiClient.post(root(farmId, "corrections"), { ...options, json: payload }),
  getProductionAnalytics: (farmId, query, options) => apiClient.get(`${root(farmId, "analytics")}/production`, { ...options, query }),
  getBreakdownAnalytics: (farmId, query, options) => apiClient.get(`${root(farmId, "analytics")}/breakdown`, { ...options, query }),
  getAvailability: (farmId, options) => apiClient.get(`${root(farmId, "analytics")}/availability`, options),
  getAnalyticsDataset: (farmId, query, options) => apiClient.get(`${root(farmId, "analytics")}/dataset`, { ...options, query }),
});
