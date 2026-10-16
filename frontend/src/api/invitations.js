import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export const invitationsApi = Object.freeze({
  list: (farmId, query, options) => apiClient.get(apiRoutes.invitations.collection(farmId), { ...options, query }),
  create: (farmId, payload, options) => apiClient.post(apiRoutes.invitations.collection(farmId), { ...options, json: payload }),
  get: (farmId, invitationId, options) => apiClient.get(apiRoutes.invitations.detail(farmId, invitationId), options),
  reissue: (farmId, invitationId, options) => apiClient.post(`${apiRoutes.invitations.detail(farmId, invitationId)}/reissue`, options),
  revoke: (farmId, invitationId, options) => apiClient.post(`${apiRoutes.invitations.detail(farmId, invitationId)}/revoke`, options),
  accept: (token, options) => apiClient.post(apiRoutes.invitations.accept, { ...options, json: { token } }),
});
