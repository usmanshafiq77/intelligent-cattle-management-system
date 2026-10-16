const STATUS_DEFINITIONS = Object.freeze({
  400: ["INVALID_REQUEST", "The request could not be completed."],
  401: ["AUTHENTICATION_REQUIRED", "Your session is missing or has expired."],
  403: ["PERMISSION_DENIED", "You do not have permission to perform this action."],
  404: ["NOT_FOUND", "The requested resource is unavailable."],
  409: ["CONFLICT", "The request conflicts with the current data."],
  422: ["VALIDATION_ERROR", "Some provided values are invalid."],
  429: ["RATE_LIMITED", "Too many requests. Please wait and try again."],
  500: ["SERVER_ERROR", "The server could not complete the request."],
  503: ["SERVICE_UNAVAILABLE", "The service is temporarily unavailable."],
});

function safeDetail(detail) {
  if (typeof detail !== "string") return null;
  const normalized = detail.replace(/\s+/g, " ").trim();
  return normalized ? normalized.slice(0, 500) : null;
}

export function normalizeValidationErrors(detail) {
  if (!Array.isArray(detail)) return {};

  return detail.reduce((fields, issue) => {
    if (!issue || typeof issue !== "object") return fields;
    const location = Array.isArray(issue.loc) ? issue.loc.filter((part) => part !== "body") : [];
    const field = location.length ? location.join(".") : "form";
    const message = safeDetail(issue.msg) || "Invalid value";
    fields[field] = [...(fields[field] || []), message];
    return fields;
  }, {});
}

export class ApiError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ApiError";
    this.code = options.code || "API_ERROR";
    this.status = options.status ?? null;
    this.category = options.category || "unknown";
    this.fieldErrors = options.fieldErrors || {};
    this.serverMessage = options.serverMessage || null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.isCancelled = options.isCancelled || false;
    this.cause = options.cause;
  }
}

function retryAfterSeconds(headers) {
  const value = headers?.get?.("Retry-After");
  if (!value) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

export function httpError(status, payload, headers) {
  const [code, defaultMessage] = STATUS_DEFINITIONS[status] || ["HTTP_ERROR", "The API request failed."];
  const detail = payload?.detail;
  const serverMessage = safeDetail(detail);
  const fieldErrors = status === 422 ? normalizeValidationErrors(detail) : {};
  const canUseServerMessage = [400, 404, 409, 422, 429].includes(status);

  return new ApiError(canUseServerMessage && serverMessage ? serverMessage : defaultMessage, {
    code,
    status,
    category: status === 401
      ? "authentication"
      : status === 403
        ? "authorization"
        : status === 422
          ? "validation"
          : status >= 500
            ? "server"
            : "request",
    fieldErrors,
    serverMessage,
    retryAfterSeconds: status === 429 ? retryAfterSeconds(headers) : null,
  });
}

export function timeoutError(timeoutMs, cause) {
  return new ApiError(`The server did not respond within ${Math.ceil(timeoutMs / 1000)} seconds.`, {
    code: "TIMEOUT",
    category: "network",
    cause,
  });
}

export function cancellationError(cause) {
  return new ApiError("The request was cancelled.", {
    code: "CANCELLED",
    category: "cancellation",
    isCancelled: true,
    cause,
  });
}

export function networkError(cause) {
  return new ApiError("The ICMS server is unreachable. Check the API address and network connection.", {
    code: "NETWORK_ERROR",
    category: "network",
    cause,
  });
}
