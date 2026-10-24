import { ACQUISITION_METHODS, CATEGORIES, CATTLE_STATUSES, SEXES, SPECIES } from "./cattleOptions";

function requiredString(value, field) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`Invalid cattle ${field}.`);
  return value;
}

function enumValue(value, allowed, field) {
  if (!allowed.includes(value)) throw new Error(`Invalid cattle ${field}.`);
  return value;
}

export function requireBreed(value) {
  if (!value || typeof value !== "object") throw new Error("Invalid breed response.");
  return Object.freeze({
    ...value,
    id: requiredString(value.id, "breed id"),
    name: requiredString(value.name, "breed name"),
    species: enumValue(value.species, SPECIES, "breed species"),
    is_active: value.is_active === true,
  });
}

export function requireBreedList(value) {
  if (!Array.isArray(value)) throw new Error("Invalid breed list response.");
  return value.map(requireBreed);
}

export function requireCattle(value, expectedFarmId) {
  if (!value || typeof value !== "object") throw new Error("Invalid cattle response.");
  const farmId = requiredString(value.farm_id, "farm id");
  if (expectedFarmId && farmId !== expectedFarmId) throw new Error("Cattle response belongs to another farm.");
  return Object.freeze({
    ...value,
    id: requiredString(value.id, "id"),
    farm_id: farmId,
    tag_number: requiredString(value.tag_number, "tag number"),
    species: enumValue(value.species, SPECIES, "species"),
    sex: enumValue(value.sex, SEXES, "sex"),
    category: enumValue(value.category, CATEGORIES, "category"),
    status: enumValue(value.status, CATTLE_STATUSES, "status"),
    acquisition_method: enumValue(value.acquisition_method, ACQUISITION_METHODS, "acquisition method"),
    breed: value.breed == null ? null : requireBreed(value.breed),
  });
}

export function requireCattleList(value, expectedFarmId) {
  if (!Array.isArray(value)) throw new Error("Invalid cattle list response.");
  return value.map((animal) => requireCattle(animal, expectedFarmId));
}

export function requireCattleSummary(value) {
  if (!value || typeof value !== "object") throw new Error("Invalid cattle summary response.");
  const counts = value.status_counts;
  if (![value.total, value.female_count, value.male_count, value.breed_count].every((item) => Number.isInteger(item) && item >= 0) || !counts || typeof counts !== "object") {
    throw new Error("Invalid cattle summary response.");
  }
  const statusCounts = {};
  CATTLE_STATUSES.forEach((status) => {
    const count = counts[status] ?? 0;
    if (!Number.isInteger(count) || count < 0) throw new Error("Invalid cattle summary response.");
    statusCounts[status] = count;
  });
  if (Object.values(statusCounts).reduce((total, count) => total + count, 0) !== value.total) throw new Error("Invalid cattle summary response.");
  return Object.freeze({
    total: value.total,
    femaleCount: value.female_count,
    maleCount: value.male_count,
    breedCount: value.breed_count,
    statusCounts: Object.freeze(statusCounts),
  });
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const trimOrNull = (value) => typeof value === "string" && value.trim() ? value.trim().replace(/\s+/g, " ") : null;

function validDate(value) {
  if (!ISO_DATE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function validateCattleForm(values, { editing = false } = {}) {
  const errors = {};
  const tag = trimOrNull(values.tag_number);
  if (!tag) errors.tag_number = "Tag number is required.";
  else if (tag.length > 100) errors.tag_number = "Tag number must be 100 characters or fewer.";
  if (!editing && !SPECIES.includes(values.species)) errors.species = "Select a species.";
  if (!editing && !SEXES.includes(values.sex)) errors.sex = "Select a sex.";
  if (!CATEGORIES.includes(values.category)) errors.category = "Select a category.";
  if ((values.sex === "FEMALE" && ["BULL", "STEER"].includes(values.category)) || (values.sex === "MALE" && ["HEIFER", "COW"].includes(values.category))) {
    errors.category = "The selected category does not match the animal's sex.";
  }
  for (const field of ["date_of_birth", "acquisition_date"]) {
    if (values[field] && !validDate(values[field])) errors[field] = "Use a valid date in YYYY-MM-DD format.";
    else if (values[field] && values[field] > new Date().toISOString().slice(0, 10)) errors[field] = "Date cannot be in the future.";
  }
  if (values.birth_date_estimated && !values.date_of_birth) errors.date_of_birth = "An estimated birth date still requires a date.";
  if (!editing && values.initial_weight_kg) {
    const weight = Number(values.initial_weight_kg);
    if (!Number.isFinite(weight) || weight <= 0 || weight > 3000) errors.initial_weight_kg = "Weight must be greater than 0 and no more than 3000 kg.";
  }
  const hasCost = Boolean(String(values.initial_acquisition_cost || "").trim());
  const currency = trimOrNull(values.initial_acquisition_currency);
  if (hasCost && (!Number.isFinite(Number(values.initial_acquisition_cost)) || Number(values.initial_acquisition_cost) < 0)) errors.initial_acquisition_cost = "Cost must be zero or greater.";
  if (hasCost !== Boolean(currency)) errors.initial_acquisition_currency = "Cost and a three-letter currency must be provided together.";
  else if (currency && !/^[A-Za-z]{3}$/.test(currency)) errors.initial_acquisition_currency = "Use a three-letter ISO currency code.";
  return errors;
}

export function cattlePayload(values, { editing = false } = {}) {
  const nullable = (field) => trimOrNull(values[field]);
  const payload = {
    tag_number: values.tag_number.trim().replace(/\s+/g, " "),
    name: nullable("name"),
    category: values.category,
    breed_id: values.breed_id || null,
    date_of_birth: values.date_of_birth || null,
    birth_date_estimated: Boolean(values.birth_date_estimated),
    acquisition_date: values.acquisition_date || null,
    acquisition_method: values.acquisition_method,
    acquisition_source: nullable("acquisition_source"),
    initial_acquisition_cost: String(values.initial_acquisition_cost || "").trim() || null,
    initial_acquisition_currency: nullable("initial_acquisition_currency")?.toUpperCase() || null,
    color: nullable("color"),
    identification_marks: nullable("identification_marks"),
    notes: nullable("notes"),
  };
  if (!editing) {
    payload.species = values.species;
    payload.sex = values.sex;
    payload.mother_id = null;
    payload.father_id = null;
    payload.initial_weight_kg = String(values.initial_weight_kg || "").trim() || null;
    payload.initial_weight_measured_at = null;
    payload.initial_weight_method = nullable("initial_weight_method");
  }
  return payload;
}

export function initialFormValues(animal) {
  return {
    tag_number: animal?.tag_number || "",
    name: animal?.name || "",
    species: animal?.species || "CATTLE",
    sex: animal?.sex || "FEMALE",
    category: animal?.category || "COW",
    breed_id: animal?.breed?.id || "",
    date_of_birth: animal?.date_of_birth || "",
    birth_date_estimated: Boolean(animal?.birth_date_estimated),
    acquisition_date: animal?.acquisition_date || "",
    acquisition_method: animal?.acquisition_method || "UNKNOWN",
    acquisition_source: animal?.acquisition_source || "",
    initial_acquisition_cost: animal?.initial_acquisition_cost == null ? "" : String(animal.initial_acquisition_cost),
    initial_acquisition_currency: animal?.initial_acquisition_currency || "",
    color: animal?.color || "",
    identification_marks: animal?.identification_marks || "",
    notes: animal?.notes || "",
    initial_weight_kg: "",
    initial_weight_method: "",
  };
}
