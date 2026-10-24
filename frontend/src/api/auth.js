import { apiClient } from "./client";
import { apiRoutes } from "./routes";

/** Authentication API contracts; secure token storage is configured by AuthProvider. */
export const authApi = Object.freeze({
  register: (payload, options) => apiClient.post(apiRoutes.auth.register, { ...options, auth: false, json: payload }),
  login: (payload, options) => apiClient.post(apiRoutes.auth.login, { ...options, auth: false, json: payload }),
  getCurrentUser: (options) => apiClient.get(apiRoutes.auth.me, options),
  getAvatar: (options) => apiClient.get(apiRoutes.auth.avatar, { ...options, responseType: "blob" }),
  uploadAvatar: (body, contentType, options) => apiClient.put(apiRoutes.auth.avatar, {
    ...options,
    body,
    headers: { ...options?.headers, "Content-Type": contentType || "application/octet-stream" },
    timeoutMs: options?.timeoutMs || 60000,
  }),
  removeAvatar: (options) => apiClient.delete(apiRoutes.auth.avatar, options),
  verifyEmail: (token, options) => apiClient.post(apiRoutes.auth.verifyEmail, { ...options, auth: false, json: { token } }),
  resendVerification: (email, options) => apiClient.post(apiRoutes.auth.resendVerification, { ...options, auth: false, json: { email } }),
  forgotPassword: (email, options) => apiClient.post(apiRoutes.auth.forgotPassword, { ...options, auth: false, json: { email } }),
  resetPassword: (token, newPassword, options) => apiClient.post(apiRoutes.auth.resetPassword, { ...options, auth: false, json: { token, new_password: newPassword } }),
  updateProfile: (payload, options) => apiClient.patch(apiRoutes.auth.me, { ...options, json: payload }),
  getPreferences: (options) => apiClient.get(apiRoutes.auth.preferences, options),
  updatePreferences: (payload, options) => apiClient.put(apiRoutes.auth.preferences, { ...options, json: payload }),
  changePassword: (payload, options) => apiClient.post(apiRoutes.auth.changePassword, { ...options, json: payload }),
  requestEmailChange: (payload, options) => apiClient.post(apiRoutes.auth.emailChange, { ...options, json: payload }),
  revokeSessions: (payload, options) => apiClient.post(apiRoutes.auth.revokeSessions, { ...options, json: payload }),
  securityEvents: (options) => apiClient.get(apiRoutes.auth.securityEvents, options),
  deactivate: (payload, options) => apiClient.post(apiRoutes.auth.deactivate, { ...options, json: payload }),
  requestDeletion: (payload, options) => apiClient.post(apiRoutes.auth.deletionRequest, { ...options, json: payload }),
});
