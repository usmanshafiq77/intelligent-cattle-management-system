import { requireApiBaseUrl } from '../config/environment';

const API_PREFIX = '/api/v1';

function buildUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${requireApiBaseUrl()}${API_PREFIX}${normalizedPath}`;
}

export async function apiRequest(path, options = {}) {
  const { token, headers, ...requestOptions } = options;
  const response = await fetch(buildUrl(path), {
    ...requestOptions,
    headers: {
      Accept: 'application/json',
      ...(requestOptions.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const error = new Error(`ICMS API request failed with status ${response.status}`);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export { API_PREFIX };
