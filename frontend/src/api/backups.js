import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const backupsApi = Object.freeze({
  dashboard: (options) => apiClient.get(apiRoutes.backups.dashboard, options),
  jobs: (options) => apiClient.get(apiRoutes.backups.jobs, options),
  job: (id, options) => apiClient.get(apiRoutes.backups.job(id), options),
  request: (payload, options) => apiClient.post(apiRoutes.backups.jobs, { ...options, json: payload }),
  verify: (id, payload, options) => apiClient.post(apiRoutes.backups.verify(id), { ...options, json: payload }),
  restoreTest: (id, payload, options) => apiClient.post(apiRoutes.backups.restoreTest(id), { ...options, json: payload }),
  restoreTests: (options) => apiClient.get(apiRoutes.backups.restoreTests, options),
  configuration: (options) => apiClient.get(apiRoutes.backups.configuration, options),
  updateConfiguration: (payload, options) => apiClient.put(apiRoutes.backups.configuration, { ...options, json: payload }),
  retention: (options) => apiClient.get(apiRoutes.backups.retention, options),
  googleStatus: (options) => apiClient.get(apiRoutes.backups.googleStatus, options),
  googleFiles: (options) => apiClient.get(apiRoutes.backups.googleFiles, options),
  googleConnect: (payload, options) => apiClient.post(apiRoutes.backups.googleConnect, { ...options, json: payload }),
  googleDisconnect: (payload, options) => apiClient.post(apiRoutes.backups.googleDisconnect, { ...options, json: payload }),
});
