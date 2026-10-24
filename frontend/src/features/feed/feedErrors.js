export function feedErrorMessage(error) {
  if (error?.status === 403) return "Your verified farm permissions do not allow this feed operation.";
  if (error?.status === 404) return "The requested farm feed record was not found.";
  if (error?.status === 409) return error?.message || "This feed operation conflicts with current inventory.";
  if (error?.status === 422) return error?.message || "Review the feed quantities, units, and target details.";
  if (error?.status === 429) return "Too many requests. Wait briefly and try again.";
  if (error?.status === 503 || error?.category === "network" || error?.code === "TIMEOUT") {
    return "Feed information is temporarily unavailable. Check the connection and retry.";
  }
  return "The feed operation could not be completed safely.";
}
