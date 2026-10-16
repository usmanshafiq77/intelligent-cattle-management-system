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
    || typeof payload.full_name !== "string"
    || typeof payload.email !== "string"
    || typeof payload.status !== "string"
    || typeof payload.is_email_verified !== "boolean"
  ) {
    throw new Error("The registration response did not match the reviewed authentication contract.");
  }
  return payload;
}
