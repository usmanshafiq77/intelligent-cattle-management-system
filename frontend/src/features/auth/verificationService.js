import { requireMessageResponse } from "./authContracts";

export function normalizeVerificationEmail(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function isVerificationEmail(value) {
  return /^\S+@\S+\.\S+$/.test(normalizeVerificationEmail(value));
}

export async function requestVerificationResend(api, email, signal) {
  return requireMessageResponse(await api.resendVerification(normalizeVerificationEmail(email), { signal }));
}
