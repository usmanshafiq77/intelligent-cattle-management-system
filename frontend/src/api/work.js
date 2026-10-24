import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const workApi = Object.freeze({
  listTasks: (farmId, query, options) => apiClient.get(apiRoutes.work.root(farmId, "tasks"), { ...options, query }),
  createTask: (farmId, payload, options) => apiClient.post(apiRoutes.work.root(farmId, "tasks"), { ...options, json: payload }),
  getTask: (farmId, taskId, options) => apiClient.get(apiRoutes.work.task(farmId, taskId), options),
  updateTask: (farmId, taskId, payload, options) => apiClient.patch(apiRoutes.work.task(farmId, taskId), { ...options, json: payload }),
  assignTask: (farmId, taskId, payload, options) => apiClient.post(`${apiRoutes.work.task(farmId, taskId)}/assign`, { ...options, json: payload }),
  updateStatus: (farmId, taskId, payload, options) => apiClient.post(`${apiRoutes.work.task(farmId, taskId)}/status`, { ...options, json: payload }),
  history: (farmId, taskId, options) => apiClient.get(`${apiRoutes.work.task(farmId, taskId)}/history`, options),
  addComment: (farmId, taskId, payload, options) => apiClient.post(`${apiRoutes.work.task(farmId, taskId)}/comments`, { ...options, json: payload }),
  listCattleAssignments: (farmId, query, options) => apiClient.get(apiRoutes.work.root(farmId, "cattle-assignments"), { ...options, query }),
  assignCattle: (farmId, payload, options) => apiClient.post(apiRoutes.work.root(farmId, "cattle-assignments"), { ...options, json: payload }),
  endCattleAssignment: (farmId, assignmentId, options) => apiClient.delete(`${apiRoutes.work.root(farmId, "cattle-assignments")}/${encodeURIComponent(assignmentId)}`, options),
  notifications: (query, options) => apiClient.get(apiRoutes.work.notifications, { ...options, query }),
  getNotification: (id, options) => apiClient.get(apiRoutes.work.notification(id), options),
  markRead: (id, options) => apiClient.patch(`${apiRoutes.work.notification(id)}/read`, options),
  markAllRead: (options) => apiClient.post(`${apiRoutes.work.notifications}/read-all`, options),
  getPreferences: (options) => apiClient.get(`${apiRoutes.work.notifications}/preferences`, options),
  updatePreferences: (payload, options) => apiClient.put(`${apiRoutes.work.notifications}/preferences`, { ...options, json: payload }),
});
