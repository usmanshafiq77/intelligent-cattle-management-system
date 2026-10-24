export const AUTH_LIMITS = Object.freeze({
  fullNameMin: 2,
  fullNameMax: 150,
  emailMax: 254,
  passwordMin: 8,
  passwordMax: 128,
});

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function validateEmail(value) {
  const email = normalizeEmail(value);
  if (!email) return "Email address is required.";
  if (email.length > AUTH_LIMITS.emailMax) return "Email address is too long.";
  if (!EMAIL_PATTERN.test(email)) return "Enter a valid email address.";
  return null;
}

export function validateLogin(values) {
  const errors = {};
  const emailError = validateEmail(values.email);
  if (emailError) errors.email = emailError;
  if (!values.password) errors.password = "Password is required.";
  else if (values.password.length > AUTH_LIMITS.passwordMax) errors.password = "Password must be 128 characters or fewer.";
  return errors;
}

export function validateSignup(values) {
  const errors = {};
  const fullName = typeof values.fullName === "string" ? values.fullName.trim() : "";
  const emailError = validateEmail(values.email);

  if (!fullName) errors.fullName = "Full name is required.";
  else if (fullName.length < AUTH_LIMITS.fullNameMin) errors.fullName = "Full name must contain at least 2 characters.";
  else if (fullName.length > AUTH_LIMITS.fullNameMax) errors.fullName = "Full name must be 150 characters or fewer.";
  if (emailError) errors.email = emailError;
  if (!values.password) errors.password = "Password is required.";
  else if (values.password.length < AUTH_LIMITS.passwordMin) errors.password = "Password must contain at least 8 characters.";
  else if (values.password.length > AUTH_LIMITS.passwordMax) errors.password = "Password must be 128 characters or fewer.";
  if (!values.confirmPassword) errors.confirmPassword = "Confirm your password.";
  else if (values.confirmPassword !== values.password) errors.confirmPassword = "Passwords do not match.";
  return errors;
}

export function validateForgotPassword(values) {
  const error = validateEmail(values.email);
  return error ? { email: error } : {};
}

export function validateResetPassword(values) {
  const errors = {};
  if (!values.password) errors.password = "Password is required.";
  else if (values.password.length < AUTH_LIMITS.passwordMin) errors.password = "Password must contain at least 8 characters.";
  else if (values.password.length > AUTH_LIMITS.passwordMax) errors.password = "Password must be 128 characters or fewer.";
  if (!values.confirmPassword) errors.confirmPassword = "Confirm your password.";
  else if (values.confirmPassword !== values.password) errors.confirmPassword = "Passwords do not match.";
  return errors;
}

export function loginPayload(values) {
  return { email: normalizeEmail(values.email), password: values.password };
}

export function signupPayload(values) {
  return {
    full_name: values.fullName.trim(),
    email: normalizeEmail(values.email),
    password: values.password,
  };
}
