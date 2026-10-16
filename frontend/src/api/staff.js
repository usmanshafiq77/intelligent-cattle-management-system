import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const staffApi = Object.freeze({
  list: (farmId, query, options) => apiClient.get(apiRoutes.staff.collection(farmId), { ...options, query }),
  get: (farmId, membershipId, options) => apiClient.get(apiRoutes.staff.detail(farmId, membershipId), options),
  updateRole: (farmId, membershipId, role, options) => apiClient.patch(apiRoutes.staff.role(farmId, membershipId), { ...options, json: { role } }),
  updateStatus: (farmId, membershipId, status, options) => apiClient.patch(apiRoutes.staff.status(farmId, membershipId), { ...options, json: { status } }),
  assignCustomRoles: (farmId, membershipId, roleIds, options) => apiClient.post(apiRoutes.staff.customRoles(farmId, membershipId), { ...options, json: { role_ids: roleIds } }),
  removeCustomRoles: (farmId, membershipId, roleIds, options) => apiClient.delete(apiRoutes.staff.customRoles(farmId, membershipId), { ...options, json: { role_ids: roleIds } }),
  listRoles: (farmId, options) => apiClient.get(apiRoutes.roles.collection(farmId), options),
  createRole: (farmId, payload, options) => apiClient.post(apiRoutes.roles.collection(farmId), { ...options, json: payload }),
  getRole: (farmId, roleId, options) => apiClient.get(apiRoutes.roles.detail(farmId, roleId), options),
  updateRoleDefinition: (farmId, roleId, payload, options) => apiClient.patch(apiRoutes.roles.detail(farmId, roleId), { ...options, json: payload }),
  deleteRole: (farmId, roleId, options) => apiClient.delete(apiRoutes.roles.detail(farmId, roleId), options),
});
