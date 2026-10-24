import {
  buildApiUrl,
  createApiClient,
  createMultipartBody,
  serializeQuery,
} from "../src/api/client";
import {
  resetAuthTransportForTests,
  signalSessionExpired,
  subscribeToSessionExpiration,
} from "../src/api/authTransport";

function response(status, payload, extraHeaders = {}) {
  const normalizedHeaders = Object.fromEntries(
    Object.entries(extraHeaders).map(([key, value]) => [key.toLowerCase(), value]),
  );
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => normalizedHeaders[name.toLowerCase()] || null },
    json: jest.fn().mockResolvedValue(payload),
    text: jest.fn().mockResolvedValue(typeof payload === "string" ? payload : JSON.stringify(payload)),
    blob: jest.fn().mockResolvedValue({ type: "blob" }),
  };
}

function clientWith(fetchImpl, overrides = {}) {
  return createApiClient({
    fetchImpl,
    baseUrlResolver: () => "http://api.test:8000",
    debug: false,
    ...overrides,
  });
}

afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
  resetAuthTransportForTests();
});

test("builds the registration URL with exactly one API prefix", () => {
  expect(buildApiUrl("/auth/register", { baseUrl: "http://127.0.0.1:8000" }))
    .toBe("http://127.0.0.1:8000/api/v1/auth/register");
});

test("attaches a Bearer token, serializes query values, and parses JSON", async () => {
  const fetchImpl = jest.fn().mockResolvedValue(response(200, { items: [] }));
  const client = clientWith(fetchImpl, { tokenGetter: async () => "secret-token" });

  await expect(client.get("/cattle", { query: { limit: 20, status: ["ACTIVE", "SOLD"], ignored: null } }))
    .resolves.toEqual({ items: [] });
  expect(fetchImpl).toHaveBeenCalledTimes(1);
  expect(fetchImpl.mock.calls[0][0]).toBe(
    "http://api.test:8000/api/v1/cattle?limit=20&status=ACTIVE&status=SOLD",
  );
  expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBe("Bearer secret-token");
});

test("safe development logs never include tokens, headers, query values, or payloads", async () => {
  const logger = jest.fn();
  const fetchImpl = jest.fn().mockResolvedValue(response(200, { ok: true }));
  const client = clientWith(fetchImpl, {
    tokenGetter: async () => "super-secret-token",
    debug: true,
    logger,
  });

  await client.post("/auth/login", {
    query: { verification_token: "secret-query" },
    json: { password: "secret-password" },
  });

  const logged = JSON.stringify(logger.mock.calls);
  expect(logged).not.toContain("super-secret-token");
  expect(logged).not.toContain("secret-query");
  expect(logged).not.toContain("secret-password");
});

test("classifies timeout and external cancellation separately", async () => {
  jest.useFakeTimers();
  const fetchImpl = jest.fn((url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
  }));
  const client = clientWith(fetchImpl, { tokenGetter: async () => null });

  const timedRequest = client.get("/health", { auth: false, timeoutMs: 50 });
  jest.advanceTimersByTime(51);
  await expect(timedRequest).rejects.toMatchObject({ code: "TIMEOUT", category: "network" });

  const controller = new AbortController();
  const cancelledRequest = client.get("/health", { auth: false, signal: controller.signal });
  controller.abort();
  await expect(cancelledRequest).rejects.toMatchObject({ code: "CANCELLED", isCancelled: true });
});

test("signals an authenticated 401 only once and keeps 403 distinct", async () => {
  const listener = jest.fn();
  subscribeToSessionExpiration(listener);
  const fetchImpl = jest.fn()
    .mockResolvedValueOnce(response(401, { detail: "Invalid token" }))
    .mockResolvedValueOnce(response(401, { detail: "Invalid token" }))
    .mockResolvedValueOnce(response(403, { detail: "Inactive" }));
  const client = clientWith(fetchImpl, {
    tokenGetter: async () => "same-token",
    unauthorizedHandler: signalSessionExpired,
  });

  await expect(client.get("/auth/me")).rejects.toMatchObject({ code: "AUTHENTICATION_REQUIRED", status: 401 });
  await expect(client.get("/auth/me")).rejects.toMatchObject({ code: "AUTHENTICATION_REQUIRED", status: 401 });
  await expect(client.get("/auth/me")).rejects.toMatchObject({ code: "PERMISSION_DENIED", status: 403 });
  expect(listener).toHaveBeenCalledTimes(1);
});

test.each([
  [400, "INVALID_REQUEST"],
  [404, "NOT_FOUND"],
  [409, "CONFLICT"],
  [429, "RATE_LIMITED"],
  [500, "SERVER_ERROR"],
  [503, "SERVICE_UNAVAILABLE"],
])("normalizes HTTP %s as %s", async (status, code) => {
  const client = clientWith(jest.fn().mockResolvedValue(response(status, { detail: "Backend detail" }, { "Retry-After": "12" })), {
    tokenGetter: async () => null,
  });
  await expect(client.get("/health", { auth: false })).rejects.toMatchObject({
    status,
    code,
    retryAfterSeconds: status === 429 ? 12 : null,
  });
});

test("normalizes FastAPI 422 field errors without retaining rejected input", async () => {
  const payload = {
    detail: [
      { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error", input: "private@example" },
      { loc: ["body", "password"], msg: "String should have at least 8 characters", type: "string_too_short", input: "secret" },
    ],
  };
  const client = clientWith(jest.fn().mockResolvedValue(response(422, payload)), { tokenGetter: async () => null });
  const error = await client.post("/auth/register", { auth: false, json: {} }).catch((caught) => caught);

  expect(error).toMatchObject({ code: "VALIDATION_ERROR", category: "validation" });
  expect(error.fieldErrors.email).toEqual(["value is not a valid email address"]);
  expect(error.fieldErrors.password).toEqual(["String should have at least 8 characters"]);
  expect(JSON.stringify(error)).not.toContain("private@example");
  expect(JSON.stringify(error)).not.toContain("secret");
});

test("classifies an unavailable network and never replays a failed write", async () => {
  const fetchImpl = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  const client = clientWith(fetchImpl, { tokenGetter: async () => null });

  await expect(client.post("/farms", { json: { name: "Farm" } })).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});

test("prepares multipart bodies without setting a boundary manually", () => {
  const body = createMultipartBody({ purpose: "PROFILE", tags: ["front", "primary"] });
  expect(body).toBeInstanceOf(FormData);
  expect(serializeQuery({ active: false, count: 0 })).toBe("active=false&count=0");
});
