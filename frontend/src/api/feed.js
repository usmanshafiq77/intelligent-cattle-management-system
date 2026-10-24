import { apiClient } from "./client";
import { apiRoutes } from "./routes";

const root = apiRoutes.feed.root;

export const feedApi = Object.freeze({
  listItems: (farmId, query, options) => apiClient.get(root(farmId, "items"), { ...options, query }),
  createItem: (farmId, payload, options) => apiClient.post(root(farmId, "items"), { ...options, json: payload }),
  updateItem: (farmId, itemId, payload, options) => apiClient.patch(apiRoutes.feed.item(farmId, itemId), { ...options, json: payload }),
  listPurchases: (farmId, query, options) => apiClient.get(root(farmId, "stock/purchases"), { ...options, query }),
  createPurchase: (farmId, payload, options) => apiClient.post(root(farmId, "stock/purchases"), { ...options, json: payload }),
  adjustStock: (farmId, payload, options) => apiClient.post(root(farmId, "stock/adjustments"), { ...options, json: payload }),
  stockHistory: (farmId, query, options) => apiClient.get(root(farmId, "stock/history"), { ...options, query }),
  lowStock: (farmId, options) => apiClient.get(root(farmId, "alerts/low-stock"), options),
  listSchedules: (farmId, query, options) => apiClient.get(root(farmId, "schedules"), { ...options, query }),
  createSchedule: (farmId, payload, options) => apiClient.post(root(farmId, "schedules"), { ...options, json: payload }),
  updateSchedule: (farmId, scheduleId, payload, options) => apiClient.patch(apiRoutes.feed.schedule(farmId, scheduleId), { ...options, json: payload }),
  listConsumption: (farmId, query, options) => apiClient.get(root(farmId, "consumption"), { ...options, query }),
  createConsumption: (farmId, payload, options) => apiClient.post(root(farmId, "consumption"), { ...options, json: payload }),
  listNutritionPlans: (farmId, options) => apiClient.get(root(farmId, "nutrition-plans"), options),
  createNutritionPlan: (farmId, payload, options) => apiClient.post(root(farmId, "nutrition-plans"), { ...options, json: payload }),
  updateNutritionPlan: (farmId, planId, payload, options) => apiClient.patch(apiRoutes.feed.nutritionPlan(farmId, planId), { ...options, json: payload }),
  consumptionReport: (farmId, query, options) => apiClient.get(root(farmId, "reports/summary"), { ...options, query }),
  costReport: (farmId, query, options) => apiClient.get(root(farmId, "reports/costs"), { ...options, query }),
});
