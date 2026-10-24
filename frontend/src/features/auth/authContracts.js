export function requireLoginResponse(payload) {
  if (
    !payload
    || typeof payload.access_token !== "string"
    || !payload.access_token.trim()
    || payload.token_type?.toLowerCase() !== "bearer"
  ) {
    throw new Error("The login response did not match the reviewed authentication contract.");
  }
  return { accessToken: payload.access_token, tokenType: "bearer" };
}

export function requireRegistrationResponse(payload) {
  if (
    !payload
    || typeof payload.id !== "string"
    || !payload.id.trim()
    || typeof payload.full_name !== "string"
    || !payload.full_name.trim()
    || typeof payload.email !== "string"
    || !payload.email.trim()
    || !["ACTIVE", "PENDING", "INACTIVE"].includes(payload.status)
    || typeof payload.is_email_verified !== "boolean"
    || typeof payload.is_system_admin !== "boolean"
    || typeof payload.created_at !== "string"
    || !payload.created_at.trim()
    || (payload.verification_delivery_status != null && !["SENT", "FAILED"].includes(payload.verification_delivery_status))
  ) {
    throw new Error("The registration response did not match the reviewed authentication contract.");
  }
  return payload;
}

export function requireCurrentUserResponse(payload) {
  if (
    !payload
    || typeof payload.id !== "string"
    || !payload.id.trim()
    || typeof payload.full_name !== "string"
    || !payload.full_name.trim()
    || typeof payload.email !== "string"
    || !payload.email.trim()
    || typeof payload.is_system_admin !== "boolean"
    || typeof payload.status !== "string"
    || typeof payload.is_email_verified !== "boolean"
    || typeof payload.created_at !== "string"
    || !payload.created_at.trim()
  ) {
    throw new Error("The current-user response did not match the reviewed authentication contract.");
  }
  return payload;
}

export function requireMessageResponse(payload) {
  if (!payload || typeof payload.detail !== "string" || !payload.detail.trim()) {
    throw new Error("The authentication response did not match the reviewed contract.");
  }
  return payload;
}
