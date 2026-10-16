import { apiClient } from "./client";
import { apiRoutes } from "./routes";

export async function checkApiConnectivity({ includeDatabase = false, timeoutMs = 5000, signal } = {}) {
  const service = await apiClient.get(apiRoutes.health, { auth: false, timeoutMs, signal });
  const database = includeDatabase
    ? await apiClient.get(apiRoutes.databaseHealth, { auth: false, timeoutMs, signal })
    : null;
  return { service, database };
}
