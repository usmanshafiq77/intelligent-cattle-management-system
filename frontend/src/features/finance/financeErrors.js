export function financeErrorMessage(error) {
  if (error?.status === 403) return "Your verified farm permissions do not allow this finance operation.";
  if (error?.status === 404) return "The requested farm finance record was not found.";
  if ([409, 422].includes(error?.status)) return error?.message || "Review the amounts, dates, currency, and related records.";
  return error?.message || "The finance operation could not be completed safely.";
}
