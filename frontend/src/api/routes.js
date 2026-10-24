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
    avatar: "/auth/me/avatar",
    verifyEmail: "/auth/verify-email",
    resendVerification: "/auth/verification/resend",
    forgotPassword: "/auth/forgot-password",
    resetPassword: "/auth/reset-password",
    preferences: "/auth/me/preferences",
    changePassword: "/auth/me/change-password",
    emailChange: "/auth/me/email-change",
    revokeSessions: "/auth/me/revoke-sessions",
    securityEvents: "/auth/me/security-events",
    deactivate: "/auth/me/deactivate",
    deletionRequest: "/auth/me/deletion-request",
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
    summary: (farmId) => `${farmRoot(farmId)}/cattle/summary`,
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
  feed: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/feed/${resource}`,
    item: (farmId, itemId) => `${farmRoot(farmId)}/feed/items/${segment(itemId, "itemId")}`,
    schedule: (farmId, scheduleId) => `${farmRoot(farmId)}/feed/schedules/${segment(scheduleId, "scheduleId")}`,
    nutritionPlan: (farmId, planId) => `${farmRoot(farmId)}/feed/nutrition-plans/${segment(planId, "planId")}`,
  }),
  breeding: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/breeding/${resource}`,
    event: (farmId, eventId) => `${farmRoot(farmId)}/breeding/events/${segment(eventId, "eventId")}`,
    calvingClinical: (farmId, eventId) => `${farmRoot(farmId)}/breeding/calvings/${segment(eventId, "eventId")}/clinical`,
    offspring: (farmId, eventId) => `${farmRoot(farmId)}/breeding/calvings/${segment(eventId, "eventId")}/offspring`,
    pedigree: (farmId, cattleId) => `${farmRoot(farmId)}/breeding/pedigree/${segment(cattleId, "cattleId")}`,
    reminder: (farmId, reminderId) => `${farmRoot(farmId)}/breeding/reminders/${segment(reminderId, "reminderId")}`,
  }),
  finance: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/finance/${resource}`,
    transaction: (farmId, transactionId) => `${farmRoot(farmId)}/finance/transactions/${segment(transactionId, "transactionId")}`,
    asset: (farmId, assetId) => `${farmRoot(farmId)}/finance/assets/${segment(assetId, "assetId")}`,
  }),
  marketplace: Object.freeze({
    listings: "/marketplace/listings",
    listing: (listingId) => `/marketplace/listings/${segment(listingId, "listingId")}`,
    inquiry: (inquiryId) => `/marketplace/inquiries/${segment(inquiryId, "inquiryId")}`,
    buyerInquiries: "/marketplace/inquiries",
    saved: "/marketplace/saved",
    notifications: "/marketplace/notifications",
    moderationReports: "/marketplace/moderation/reports",
    sellerRoot: (farmId, resource) => `${farmRoot(farmId)}/marketplace/${resource}`,
    sellerListing: (farmId, listingId) => `${farmRoot(farmId)}/marketplace/listings/${segment(listingId, "listingId")}`,
  }),
  work: Object.freeze({
    root: (farmId, resource) => `${farmRoot(farmId)}/work/${resource}`,
    task: (farmId, taskId) => `${farmRoot(farmId)}/work/tasks/${segment(taskId, "taskId")}`,
    notifications: "/notifications",
    notification: (notificationId) => `/notifications/${segment(notificationId, "notificationId")}`,
  }),
  settings: Object.freeze({ farm: (farmId) => `${farmRoot(farmId)}/settings` }),
  backups: Object.freeze({
    dashboard: "/admin/backups/dashboard",
    jobs: "/admin/backups/jobs",
    job: (jobId) => `/admin/backups/jobs/${segment(jobId, "jobId")}`,
    verify: (jobId) => `/admin/backups/jobs/${segment(jobId, "jobId")}/verify`,
    restoreTest: (jobId) => `/admin/backups/jobs/${segment(jobId, "jobId")}/restore-test`,
    restoreTests: "/admin/backups/restore-tests",
    configuration: "/admin/backups/configuration",
    retention: "/admin/backups/retention",
    googleConnect: "/admin/backups/google/connect",
    googleStatus: "/admin/backups/google/status",
    googleFiles: "/admin/backups/google/files",
    googleDisconnect: "/admin/backups/google/disconnect",
  }),
});
