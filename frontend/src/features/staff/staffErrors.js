export function staffErrorMessage(error, { invitation = false, ambiguous = false } = {}) {
  if (ambiguous) return invitation ? "We could not confirm the invitation action. Refresh before trying again." : "We could not confirm the staff change. Refresh before trying again.";
  if (error?.code === "TIMEOUT" || error?.category === "network") return invitation ? "We could not confirm the invitation action. Refresh before trying again." : "Staff data is temporarily unavailable. Please retry.";
  if (error?.status === 401) return "Your session has expired. Please sign in again.";
  if (error?.status === 403) return "You do not have permission for this farm action.";
  if (error?.status === 404) return invitation ? "This invitation is unavailable." : "This staff member is unavailable.";
  if (error?.status === 409) return "This action conflicts with the current farm state. Refresh and try again.";
  if (error?.status === 429) return "Too many requests. Please wait and try again.";
  if (error?.status >= 500) return "The server could not complete this request.";
  return "The request could not be completed. Please review and try again.";
}
