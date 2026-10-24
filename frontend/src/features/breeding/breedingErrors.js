export function breedingErrorMessage(error) {
  if (error?.status === 403) return "Your active farm role does not allow this breeding action.";
  if (error?.status === 404) return "The farm-scoped breeding record was not found.";
  if (error?.status === 409) return error?.body?.detail || "This request conflicts with an existing record.";
  if (error?.status === 422) return error?.body?.detail || "Review the animal, dates, quantities, and required fields.";
  return error?.message || "Breeding information is temporarily unavailable.";
}
