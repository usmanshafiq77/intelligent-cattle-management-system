export function healthErrorMessage(error) {
  if (error?.status === 403) return "You do not have permission to perform this health action.";
  if (error?.status === 404) return "The selected cattle or health record is no longer available in this farm.";
  if (error?.status === 409) return error?.detail || "This record conflicts with an existing clinical event.";
  if (error?.status === 422) return error?.detail || "Review the health information and dates, then try again.";
  if (error?.code === "TIMEOUT" || error?.category === "network") return "Health records are temporarily unavailable. Check the connection and retry.";
  return error?.detail || "The health request could not be completed safely.";
}
