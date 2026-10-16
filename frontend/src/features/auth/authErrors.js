const FIELD_ALIASES = Object.freeze({
  full_name: "fullName",
  email: "email",
  password: "password",
});

export function authFieldErrors(error) {
  const mapped = {};
  Object.entries(error?.fieldErrors || {}).forEach(([field, messages]) => {
    const normalizedField = field.split(".").at(-1);
    const target = FIELD_ALIASES[normalizedField];
    if (target && Array.isArray(messages) && messages.length) mapped[target] = messages[0];
  });

  if (error?.status === 422 && /full name/i.test(error.serverMessage || "")) {
    mapped.fullName = error.serverMessage;
  }
  return mapped;
}

export function authErrorMessage(error, action) {
  if (error?.isCancelled) return null;
  if (action === "login" && error?.status === 401) return "The email or password is incorrect.";
  if (action === "login" && error?.status === 403) return "This account is currently inactive. Contact an administrator for help.";
  if (action === "signup" && error?.status === 409) return "An account with this email address already exists.";
  if (error?.status === 422) return "Review the highlighted information and try again.";
  if (error?.status === 429) {
    const wait = error.retryAfterSeconds ? ` Try again in ${error.retryAfterSeconds} seconds.` : " Please wait before trying again.";
    return `Too many authentication attempts.${wait}`;
  }
  if (error?.code === "NETWORK_ERROR") return "ICMS cannot reach the server. Check your connection and API address.";
  if (error?.code === "TIMEOUT") return "The authentication request timed out. Please try again.";
  if (error?.status === 503) return "Authentication is temporarily unavailable. Please try again shortly.";
  if (error?.status >= 500) return "The server could not complete authentication. Please try again.";
  return "Authentication could not be completed. Please try again.";
}
