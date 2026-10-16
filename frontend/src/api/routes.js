function segment(value, name) {
  if (value === undefined || value === null || value === "") throw new TypeError(`${name} is required.`);
  return encodeURIComponent(String(value));
}

const farmRoot = (farmId) => `/farms/${segment(farmId, "farmId")}`;
const cattleRoot = (farmId, cattleId) => `${farmRoot(farmId)}/cattle/${segment(cattleId, "cattleId")}`;

export const apiRoutes = Object.freeze({
  health: "/health",
  databaseHealth: "/health/db",
  auth: Object.freeze({
    register: "/auth/register",
    login: "/auth/login",
    me: "/auth/me",
    verifyEmail: "/auth/verify-email",
    resendVerification: "/auth/verification/resend",
  }),
  farms: Object.freeze({
    collection: "/farms",
    detail: (farmId) => farmRoot(farmId),
  }),
  staff: Object.freeze({
    collection: (farmId) => `${farmRoot(farmId)}/staff`,
    detail: (farmId, membershipId) => `${farmRoot(farmId)}/staff/${segment(membershipId, "membershipId")}`,
    role: (farmId, membershipId) => `${farmRoot(farmId)}/staff/${segment(membershipId, "membershipId")}/role`,
    status: (farmId, membershipId) => `${farmRoot(farmId)}/staff/${segment(membershipId, "membershipId")}/status`,
    customRoles: (farmId, membershipId) => `${farmRoot(farmId)}/staff/${segment(membershipId, "membershipId")}/roles`,
    myPermissions: (farmId) => `${farmRoot(farmId)}/staff/permissions/me`,
  }),
  roles: Object.freeze({
    collection: (farmId) => `${farmRoot(farmId)}/roles`,
    detail: (farmId, roleId) => `${farmRoot(farmId)}/roles/${segment(roleId, "roleId")}`,
  }),
  invitations: Object.freeze({
    collection: (farmId) => `${farmRoot(farmId)}/invitations`,
    detail: (farmId, invitationId) => `${farmRoot(farmId)}/invitations/${segment(invitationId, "invitationId")}`,
    accept: "/invitations/accept",
  }),
  breeds: Object.freeze({
    collection: "/breeds",
    detail: (breedId) => `/breeds/${segment(breedId, "breedId")}`,
  }),
  cattle: Object.freeze({
    collection: (farmId) => `${farmRoot(farmId)}/cattle`,
    detail: cattleRoot,
    lifecycle: (farmId, cattleId) => `${cattleRoot(farmId, cattleId)}/lifecycle`,
    weights: (farmId, cattleId) => `${cattleRoot(farmId, cattleId)}/weights`,
    media: (farmId, cattleId) => `${cattleRoot(farmId, cattleId)}/media`,
    mediaDetail: (farmId, cattleId, mediaId) => `${cattleRoot(farmId, cattleId)}/media/${segment(mediaId, "mediaId")}`,
    mediaContent: (farmId, cattleId, mediaId) => `${cattleRoot(farmId, cattleId)}/media/${segment(mediaId, "mediaId")}/content`,
  }),
  healthRecords: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/health/${resource}`,
    detail: (farmId, resource, recordId) => `${farmRoot(farmId)}/health/${resource}/${segment(recordId, "recordId")}`,
    history: (farmId, cattleId) => `${farmRoot(farmId)}/health/cattle/${segment(cattleId, "cattleId")}/history`,
  }),
  milk: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/milk/${resource}`,
    detail: (farmId, resource, recordId) => `${farmRoot(farmId)}/milk/${resource}/${segment(recordId, "recordId")}`,
  }),
});
