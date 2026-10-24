export function milkErrorMessage(error) {
  if (error?.status === 403) return "Your verified farm permissions do not allow this milk action.";
  if (error?.status === 404) return "The selected cow, lactation, or milk record is no longer available in this farm.";
  if (error?.status === 409) return error?.detail || "This entry conflicts with an existing milk record.";
  if (error?.status === 422) return error?.detail || "Review the cow, session, quantity, and dates, then try again.";
  if (error?.code === "TIMEOUT" || error?.category === "network") return "Milk records are temporarily unavailable. Check the connection and retry.";
  return error?.detail || "The milk request could not be completed safely.";
}
