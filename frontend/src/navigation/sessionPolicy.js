export function canAccessProtectedRoutes(status) {
  return status === "authenticated";
}

export function canAccessPublicAuthRoutes(status) {
  return status === "unauthenticated";
}
