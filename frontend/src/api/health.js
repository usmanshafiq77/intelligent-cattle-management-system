import { apiClient } from "./client";
import { apiRoutes } from "./routes";

const root = apiRoutes.healthRecords.root;
const detail = apiRoutes.healthRecords.detail;

export const healthApi = Object.freeze({
  listEncounters: (farmId, query, options) => apiClient.get(root(farmId, "encounters"), { ...options, query }),
  createEncounter: (farmId, payload, options) => apiClient.post(root(farmId, "encounters"), { ...options, json: payload }),
  getEncounter: (farmId, encounterId, options) => apiClient.get(detail(farmId, "encounters", encounterId), options),
  finalizeEncounter: (farmId, encounterId, payload, options) => apiClient.post(`${detail(farmId, "encounters", encounterId)}/finalize`, { ...options, json: payload }),
  listDiagnoses: (farmId, query, options) => apiClient.get(root(farmId, "diagnoses"), { ...options, query }),
  createDiagnosis: (farmId, payload, options) => apiClient.post(root(farmId, "diagnoses"), { ...options, json: payload }),
  getDiagnosis: (farmId, diagnosisId, options) => apiClient.get(detail(farmId, "diagnoses", diagnosisId), options),
  updateDiagnosisStatus: (farmId, diagnosisId, payload, options) => apiClient.patch(`${detail(farmId, "diagnoses", diagnosisId)}/status`, { ...options, json: payload }),
  listVaccinationSchedules: (farmId, query, options) => apiClient.get(root(farmId, "vaccination-schedules"), { ...options, query }),
  createVaccinationSchedule: (farmId, payload, options) => apiClient.post(root(farmId, "vaccination-schedules"), { ...options, json: payload }),
  updateVaccinationSchedule: (farmId, scheduleId, payload, options) => apiClient.patch(detail(farmId, "vaccination-schedules", scheduleId), { ...options, json: payload }),
  listVaccinationAdministrations: (farmId, query, options) => apiClient.get(root(farmId, "vaccination-administrations"), { ...options, query }),
  recordVaccinationAdministration: (farmId, payload, options) => apiClient.post(root(farmId, "vaccination-administrations"), { ...options, json: payload }),
  listTreatments: (farmId, query, options) => apiClient.get(root(farmId, "treatments"), { ...options, query }),
  createTreatment: (farmId, payload, options) => apiClient.post(root(farmId, "treatments"), { ...options, json: payload }),
  transitionTreatment: (farmId, treatmentId, payload, options) => apiClient.post(`${detail(farmId, "treatments", treatmentId)}/transition`, { ...options, json: payload }),
  recordMedicationAdministration: (farmId, treatmentId, payload, options) => apiClient.post(`${detail(farmId, "treatments", treatmentId)}/medication-administrations`, { ...options, json: payload }),
  listMedicationAdministrations: (farmId, query, options) => apiClient.get(root(farmId, "medication-administrations"), { ...options, query }),
  listVeterinaryVisits: (farmId, query, options) => apiClient.get(root(farmId, "veterinary-visits"), { ...options, query }),
  createVeterinaryVisit: (farmId, payload, options) => apiClient.post(root(farmId, "veterinary-visits"), { ...options, json: payload }),
  updateVeterinaryVisit: (farmId, visitId, payload, options) => apiClient.patch(detail(farmId, "veterinary-visits", visitId), { ...options, json: payload }),
  listReminders: (farmId, query, options) => apiClient.get(root(farmId, "reminders"), { ...options, query }),
  getCattleHistory: (farmId, cattleId, query, options) => apiClient.get(apiRoutes.healthRecords.history(farmId, cattleId), { ...options, query }),
  listCorrections: (farmId, query, options) => apiClient.get(root(farmId, "corrections"), { ...options, query }),
  createCorrection: (farmId, payload, options) => apiClient.post(root(farmId, "corrections"), { ...options, json: payload }),
});
