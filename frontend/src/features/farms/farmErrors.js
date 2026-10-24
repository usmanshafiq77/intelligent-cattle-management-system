export function farmErrorMessage(error, { ambiguous = false } = {}) {
  if (ambiguous || error?.code === "TIMEOUT" || error?.category === "network") {
    return "We could not confirm whether the farm was created. Refresh your farm list before trying again to avoid a duplicate.";
  }
  if (error?.status === 401) return "Your session has expired. Please sign in again.";
  if (error?.status === 403) return "You do not have permission to perform this farm action.";
  if (error?.status === 404) return "This farm is no longer accessible.";
  if (error?.status === 409) return "The farm request conflicts with the current server state. Refresh and try again.";
  if (error?.status === 429) return error.retryAfterSeconds ? `Too many requests. Try again in ${error.retryAfterSeconds} seconds.` : "Too many requests. Please wait and try again.";
  if (error?.status >= 500) return "The server could not complete the farm request. Please try again later.";
  return "The farm request could not be completed. Please review the form and try again.";
}
