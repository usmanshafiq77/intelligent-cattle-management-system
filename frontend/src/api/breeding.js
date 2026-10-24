import { apiClient } from "./client";
import { apiRoutes } from "./routes";

const root = apiRoutes.breeding.root;
export const breedingApi = Object.freeze({
  dashboard: (farmId, options) => apiClient.get(root(farmId, "dashboard"), options),
  listHeat: (farmId, query, options) => apiClient.get(root(farmId, "heat-observations"), { ...options, query }),
  createHeat: (farmId, payload, options) => apiClient.post(root(farmId, "heat-observations"), { ...options, json: payload }),
  listEvents: (farmId, query, options) => apiClient.get(root(farmId, "events"), { ...options, query }),
  createEvent: (farmId, payload, options) => apiClient.post(root(farmId, "events"), { ...options, json: payload }),
  updateEvent: (farmId, eventId, payload, options) => apiClient.patch(apiRoutes.breeding.event(farmId, eventId), { ...options, json: payload }),
  listExams: (farmId, query, options) => apiClient.get(root(farmId, "pregnancy-examinations"), { ...options, query }),
  createExam: (farmId, payload, options) => apiClient.post(root(farmId, "pregnancy-examinations"), { ...options, json: payload }),
  listLosses: (farmId, options) => apiClient.get(root(farmId, "pregnancy-losses"), options),
  createLoss: (farmId, payload, options) => apiClient.post(root(farmId, "pregnancy-losses"), { ...options, json: payload }),
  listCalvings: (farmId, query, options) => apiClient.get(root(farmId, "calvings"), { ...options, query }),
  createCalving: (farmId, payload, options) => apiClient.post(root(farmId, "calvings"), { ...options, json: payload }),
  updateCalvingClinical: (farmId, eventId, payload, options) => apiClient.patch(apiRoutes.breeding.calvingClinical(farmId, eventId), { ...options, json: payload }),
  registerOffspring: (farmId, eventId, payload, options) => apiClient.post(apiRoutes.breeding.offspring(farmId, eventId), { ...options, json: payload }),
  setParentage: (farmId, payload, options) => apiClient.post(root(farmId, "parentage"), { ...options, json: payload }),
  pedigree: (farmId, cattleId, query, options) => apiClient.get(apiRoutes.breeding.pedigree(farmId, cattleId), { ...options, query }),
  listReminders: (farmId, query, options) => apiClient.get(root(farmId, "reminders"), { ...options, query }),
  createReminder: (farmId, payload, options) => apiClient.post(root(farmId, "reminders"), { ...options, json: payload }),
  updateReminder: (farmId, reminderId, payload, options) => apiClient.patch(apiRoutes.breeding.reminder(farmId, reminderId), { ...options, json: payload }),
  report: (farmId, query, options) => apiClient.get(root(farmId, "reports/summary"), { ...options, query }),
  audit: (farmId, query, options) => apiClient.get(root(farmId, "audit"), { ...options, query }),
});
