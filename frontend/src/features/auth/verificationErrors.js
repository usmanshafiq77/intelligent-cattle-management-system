export function verificationErrorMessage(error, action = "verify") {
  if (error?.isCancelled || error?.code === "CANCELLED") return null;
  if (error?.status === 400) return "This verification link or code is invalid, expired, or has already been used.";
  if (error?.status === 401) return "Your session has expired. Sign in again before continuing.";
  if (error?.status === 403) return "This account cannot complete verification right now.";
  if (error?.status === 422) return "Enter a valid verification code or email address.";
  if (error?.status === 429) {
    const wait = error.retryAfterSeconds ? ` Try again in ${error.retryAfterSeconds} seconds.` : " Please wait before trying again.";
    return `Too many verification requests.${wait}`;
  }
  if (error?.code === "NETWORK_ERROR") return "ICMS cannot reach the server. Check your connection and try again.";
  if (error?.code === "TIMEOUT") return "The verification request timed out. Please try again.";
  if (error?.status === 503) return "Verification is temporarily unavailable. Please try again shortly.";
  if (error?.status >= 500) return "The server could not complete verification. Please try again.";
  return action === "resend" ? "The verification email could not be requested. Please try again." : "Verification could not be completed. Please try again.";
}
