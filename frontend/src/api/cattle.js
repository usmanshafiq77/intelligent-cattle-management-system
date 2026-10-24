import { apiClient, DEFAULT_UPLOAD_TIMEOUT_MS } from "./client";
import { apiRoutes } from "./routes";

export const cattleApi = Object.freeze({
  listBreeds: (query, options) => apiClient.get(apiRoutes.breeds.collection, { ...options, query }),
  getBreed: (breedId, options) => apiClient.get(apiRoutes.breeds.detail(breedId), options),
  createBreed: (payload, options) => apiClient.post(apiRoutes.breeds.collection, { ...options, json: payload }),
  list: (farmId, query, options) => apiClient.get(apiRoutes.cattle.collection(farmId), { ...options, query }),
  summary: (farmId, query, options) => apiClient.get(apiRoutes.cattle.summary(farmId), { ...options, query }),
  create: (farmId, payload, options) => apiClient.post(apiRoutes.cattle.collection(farmId), { ...options, json: payload }),
  get: (farmId, cattleId, options) => apiClient.get(apiRoutes.cattle.detail(farmId, cattleId), options),
  update: (farmId, cattleId, payload, options) => apiClient.patch(apiRoutes.cattle.detail(farmId, cattleId), { ...options, json: payload }),
  listLifecycle: (farmId, cattleId, query, options) => apiClient.get(apiRoutes.cattle.lifecycle(farmId, cattleId), { ...options, query }),
  addLifecycleEvent: (farmId, cattleId, payload, options) => apiClient.post(apiRoutes.cattle.lifecycle(farmId, cattleId), { ...options, json: payload }),
  listWeights: (farmId, cattleId, query, options) => apiClient.get(apiRoutes.cattle.weights(farmId, cattleId), { ...options, query }),
  addWeight: (farmId, cattleId, payload, options) => apiClient.post(apiRoutes.cattle.weights(farmId, cattleId), { ...options, json: payload }),
  listMedia: (farmId, cattleId, query, options) => apiClient.get(apiRoutes.cattle.media(farmId, cattleId), { ...options, query }),
  getMedia: (farmId, cattleId, mediaId, options) => apiClient.get(apiRoutes.cattle.mediaDetail(farmId, cattleId, mediaId), options),
  downloadMedia: (farmId, cattleId, mediaId, options) => apiClient.get(apiRoutes.cattle.mediaContent(farmId, cattleId, mediaId), { ...options, responseType: "blob" }),
  uploadMedia: (farmId, cattleId, content, { filename, purpose = "PROFILE", contentType = "application/octet-stream", ...options } = {}) => apiClient.post(
    apiRoutes.cattle.media(farmId, cattleId),
    {
      timeoutMs: DEFAULT_UPLOAD_TIMEOUT_MS,
      ...options,
      query: { filename, purpose },
      headers: { "Content-Type": contentType, ...options.headers },
      body: content,
    },
  ),
  removeMedia: (farmId, cattleId, mediaId, options) => apiClient.delete(apiRoutes.cattle.mediaDetail(farmId, cattleId, mediaId), options),
});
