import {
  AUTH_LIMITS,
  loginPayload,
  normalizeEmail,
  signupPayload,
  validateLogin,
  validateSignup,
} from "../src/features/auth/validation/authValidation";
import { authErrorMessage, authFieldErrors } from "../src/features/auth/authErrors";
import { requireLoginResponse, requireRegistrationResponse } from "../src/features/auth/authContracts";
import { ApiError } from "../src/api/errors";

test("normalizes email and creates only reviewed backend payload fields", () => {
  expect(normalizeEmail("  FARMER@Example.COM ")).toBe("farmer@example.com");
  expect(loginPayload({ email: " FARMER@Example.COM ", password: "secret" })).toEqual({
    email: "farmer@example.com",
    password: "secret",
  });
  expect(signupPayload({ fullName: "  Farm Owner  ", email: " OWNER@Example.COM ", password: "password", confirmPassword: "ignored" })).toEqual({
    full_name: "Farm Owner",
    email: "owner@example.com",
    password: "password",
  });
});

test("login validation follows the backend login limits", () => {
  expect(validateLogin({ email: "", password: "" })).toEqual({
    email: "Email address is required.",
    password: "Password is required.",
  });
  expect(validateLogin({ email: "invalid", password: "x" }).email).toMatch(/valid email/);
  expect(validateLogin({ email: "user@example.com", password: "x".repeat(AUTH_LIMITS.passwordMax + 1) }).password).toMatch(/128/);
  expect(validateLogin({ email: "user@example.com", password: "x" })).toEqual({});
});

test("signup validation enforces actual registration constraints and confirmation", () => {
  const short = validateSignup({ fullName: "A", email: "bad", password: "short", confirmPassword: "different" });
  expect(short.fullName).toMatch(/2 characters/);
  expect(short.email).toMatch(/valid email/);
  expect(short.password).toMatch(/8 characters/);
  expect(short.confirmPassword).toMatch(/do not match/);

  expect(validateSignup({ fullName: "Farm Owner", email: "owner@example.com", password: "ValidPass", confirmPassword: "ValidPass" })).toEqual({});
});

test("reviewed response guards accept bearer login and registration responses", () => {
  expect(requireLoginResponse({ access_token: "token", token_type: "bearer" })).toEqual({ accessToken: "token", tokenType: "bearer" });
  expect(() => requireLoginResponse({ token: "wrong" })).toThrow(/contract/);

  const registered = { id: "user-id", full_name: "Owner", email: "owner@example.com", status: "ACTIVE", is_email_verified: false, is_system_admin: false, created_at: "2026-10-17T00:00:00Z" };
  expect(requireRegistrationResponse(registered)).toBe(registered);
  expect(() => requireRegistrationResponse({ email: "owner@example.com" })).toThrow(/contract/);
});

test("auth errors map FastAPI fields and safe status-specific messages", () => {
  const validation = new ApiError("Invalid", { status: 422, fieldErrors: { full_name: ["Too short"], email: ["Invalid email"] } });
  expect(authFieldErrors(validation)).toEqual({ fullName: "Too short", email: "Invalid email" });
  expect(authErrorMessage(new ApiError("Unauthorized", { status: 401 }), "login")).toMatch(/email or password/);
  expect(authErrorMessage(new ApiError("Conflict", { status: 409 }), "signup")).toMatch(/already exists/);
  expect(authErrorMessage(new ApiError("Rate", { status: 429, retryAfterSeconds: 15 }), "login")).toMatch(/15 seconds/);
  expect(authErrorMessage(new ApiError("Network", { code: "NETWORK_ERROR" }), "login")).toMatch(/cannot reach/);
  expect(authErrorMessage(new ApiError("Server", { status: 503 }), "login")).toMatch(/temporarily unavailable/);
});
