const ROLES = new Set(["FARM_OWNER", "FARM_MANAGER", "WORKER", "VETERINARIAN"]);
const INVITE_ROLES = Object.freeze(["FARM_MANAGER", "WORKER", "VETERINARIAN"]);

const string = (value) => typeof value === "string" && Boolean(value.trim());

export function requireStaffList(payload) {
  if (!Array.isArray(payload)) throw new Error("The staff list did not match the reviewed backend contract.");
  return payload.map(requireStaffResponse);
}

export function requireStaffResponse(member) {
  if (!member || !string(member.membership_id) || !string(member.user_id) || !string(member.name) || !string(member.email) || !ROLES.has(member.role) || !["ACTIVE", "INACTIVE", "PENDING"].includes(member.status) || !string(member.joined_at) || !Array.isArray(member.custom_role_ids)) throw new Error("The staff response did not match the reviewed backend contract.");
  return member;
}

export function requireInvitationList(payload, expectedFarmId) {
  if (!Array.isArray(payload)) throw new Error("The invitation list did not match the reviewed backend contract.");
  return payload.map((item) => requireInvitationResponse(item, expectedFarmId));
}

export function requireInvitationResponse(item, expectedFarmId) {
  if (!item || !string(item.id) || !string(item.farm_id) || (expectedFarmId && item.farm_id !== expectedFarmId) || !string(item.email) || !ROLES.has(item.role) || !["PENDING", "ACCEPTED", "REJECTED", "EXPIRED", "REVOKED"].includes(item.status) || !string(item.expires_at) || (item.delivery_status != null && !["SENT", "FAILED"].includes(item.delivery_status))) throw new Error("The invitation response did not match the reviewed backend contract.");
  return item;
}

export function requireInvitationAcceptance(payload) {
  if (!payload || !string(payload.farm_id) || !string(payload.farm_name) || !string(payload.membership_id) || !ROLES.has(payload.role) || payload.membership_status !== "ACTIVE" || !string(payload.accepted_at)) throw new Error("The invitation acceptance response did not match the reviewed backend contract.");
  return payload;
}

export const assignableInvitationRoles = INVITE_ROLES;
