import { apiClient } from "./client";
import { apiRoutes } from "./routes";

/** Authentication transport only. Persistent secure token storage is introduced in Step 19.6. */
export const authApi = Object.freeze({
  register: (payload, options) => apiClient.post(apiRoutes.auth.register, { ...options, auth: false, json: payload }),
  login: (payload, options) => apiClient.post(apiRoutes.auth.login, { ...options, auth: false, json: payload }),
  getCurrentUser: (options) => apiClient.get(apiRoutes.auth.me, options),
  verifyEmail: (token, options) => apiClient.post(apiRoutes.auth.verifyEmail, { ...options, auth: false, json: { token } }),
  resendVerification: (email, options) => apiClient.post(apiRoutes.auth.resendVerification, { ...options, auth: false, json: { email } }),
});
