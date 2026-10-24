export function cattleErrorMessage(error, { mutation = false } = {}) {
  if (error?.isCancelled) return null;
  if (error?.status === 401) return "Your session expired. Sign in again before continuing.";
  if (error?.status === 403) return "Your current farm permissions do not allow this action.";
  if (error?.status === 404) return "This cattle record is unavailable in the active farm.";
  if (error?.status === 409) return error.serverMessage || "This change conflicts with current farm data. Refresh before trying again.";
  if (error?.status === 422) return "Some cattle information is invalid. Review the highlighted fields.";
  if (error?.status === 429) return "Too many requests. Wait briefly, then retry.";
  if (error?.code === "TIMEOUT") return mutation
    ? "The result could not be confirmed. Refresh the herd before attempting this change again."
    : "The cattle service took too long to respond. Retry when ready.";
  if (error?.category === "network") return mutation
    ? "The result could not be confirmed because the connection was lost. Refresh before retrying."
    : "Cattle data is unavailable because the server cannot be reached.";
  if (error?.status >= 500) return "The cattle service is temporarily unavailable. No local data was substituted.";
  return "Cattle data could not be verified safely. Please retry.";
}
