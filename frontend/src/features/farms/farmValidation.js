const LIMITS = Object.freeze({ name: 150, location: 255, description: 2000 });

function normalized(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function validateFarm(values) {
  const name = normalized(values?.name);
  const location = normalized(values?.location);
  const description = normalized(values?.description);
  const errors = {};
  if (!name) errors.name = "Farm name is required.";
  else if (name.length < 2) errors.name = "Farm name must contain at least 2 characters.";
  else if (name.length > LIMITS.name) errors.name = `Farm name must be ${LIMITS.name} characters or fewer.`;
  if (location.length > LIMITS.location) errors.location = `Location must be ${LIMITS.location} characters or fewer.`;
  if (description.length > LIMITS.description) errors.description = `Description must be ${LIMITS.description} characters or fewer.`;
  return errors;
}

export function farmPayload(values) {
  const name = normalized(values?.name);
  const location = normalized(values?.location);
  const description = normalized(values?.description);
  return { name, location: location || null, description: description || null };
}

export const FARM_FIELD_LIMITS = LIMITS;
