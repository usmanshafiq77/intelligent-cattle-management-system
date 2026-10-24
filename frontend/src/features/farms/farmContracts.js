const FARM_ROLES = new Set(["FARM_OWNER", "FARM_MANAGER", "WORKER", "VETERINARIAN"]);

function isNonEmptyString(value) {
  return typeof value === "string" && Boolean(value.trim());
}

export function requireFarmResponse(farm) {
  if (
    !farm
    || !isNonEmptyString(farm.id)
    || !isNonEmptyString(farm.name)
    || !isNonEmptyString(farm.owner_id)
    || !isNonEmptyString(farm.created_at)
    || (farm.location !== null && farm.location !== undefined && typeof farm.location !== "string")
    || (farm.description !== null && farm.description !== undefined && typeof farm.description !== "string")
  ) {
    throw new Error("The farm response did not match the reviewed backend contract.");
  }
  return farm;
}

export function requireFarmList(payload) {
  if (!Array.isArray(payload)) throw new Error("The farm list did not match the reviewed backend contract.");
  return payload.map(requireFarmResponse);
}

export function requireEffectivePermissions(payload, expectedFarmId) {
  if (
    !payload
    || !isNonEmptyString(payload.farm_id)
    || payload.farm_id !== expectedFarmId
    || !isNonEmptyString(payload.membership_id)
    || !FARM_ROLES.has(payload.predefined_role)
    || !Array.isArray(payload.custom_role_ids)
    || !payload.custom_role_ids.every(isNonEmptyString)
    || !Array.isArray(payload.permissions)
    || !payload.permissions.every(isNonEmptyString)
  ) {
    throw new Error("The effective-permissions response did not match the reviewed backend contract.");
  }

  return {
    farmId: payload.farm_id,
    membershipId: payload.membership_id,
    role: payload.predefined_role,
    customRoleIds: [...payload.custom_role_ids],
    permissions: [...new Set(payload.permissions)],
  };
}

export const reviewedFarmRoles = Object.freeze([...FARM_ROLES]);
