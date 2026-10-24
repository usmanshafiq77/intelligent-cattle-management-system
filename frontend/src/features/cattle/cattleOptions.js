export const SPECIES = Object.freeze(["CATTLE", "BUFFALO"]);
export const SEXES = Object.freeze(["FEMALE", "MALE"]);
export const CATEGORIES = Object.freeze(["CALF", "HEIFER", "COW", "BULL", "STEER", "OTHER"]);
export const CATTLE_STATUSES = Object.freeze(["ACTIVE", "SOLD", "DECEASED", "TRANSFERRED", "MISSING", "ARCHIVED"]);
export const ACQUISITION_METHODS = Object.freeze(["UNKNOWN", "BORN_ON_FARM", "PURCHASED", "TRANSFERRED_IN", "DONATED", "OTHER"]);

export function optionLabel(value) {
  return String(value || "")
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function categoriesForSex(sex) {
  if (sex === "FEMALE") return CATEGORIES.filter((value) => !["BULL", "STEER"].includes(value));
  if (sex === "MALE") return CATEGORIES.filter((value) => !["HEIFER", "COW"].includes(value));
  return CATEGORIES;
}
