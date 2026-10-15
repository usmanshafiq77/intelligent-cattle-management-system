export const buttonSizes = Object.freeze({
  small: { minHeight: 44, paddingHorizontal: 16, fontSize: "small" },
  medium: { minHeight: 52, paddingHorizontal: 20, fontSize: "body" },
  large: { minHeight: 58, paddingHorizontal: 24, fontSize: "subtitle" },
});

export function getButtonVariant(theme, variant) {
  const { colors } = theme;
  const variants = {
    primary: {
      foreground: colors.onPrimary,
      background: colors.primary,
      border: "transparent",
      gradient: theme.gradients.primary,
    },
    secondary: {
      foreground: colors.primaryDark,
      background: colors.surfaceSecondary,
      border: colors.surfaceSecondary,
    },
    outline: {
      foreground: colors.primary,
      background: "transparent",
      border: colors.primary,
    },
    danger: {
      foreground: colors.onStatus,
      background: colors.error,
      border: colors.error,
    },
  };

  return variants[variant] || variants.primary;
}

export function getCardVariant(theme, shadows, variant) {
  const { colors } = theme;
  const variants = {
    default: {
      backgroundColor: colors.surface,
      borderColor: colors.border,
      borderWidth: 1,
    },
    outlined: {
      backgroundColor: colors.surface,
      borderColor: colors.primary,
      borderWidth: 1.5,
    },
    elevated: {
      backgroundColor: colors.surfaceElevated,
      borderColor: colors.border,
      borderWidth: 1,
      ...shadows.medium,
    },
    highlight: {
      backgroundColor: colors.surfaceSecondary,
      borderColor: colors.border,
      borderWidth: 1,
    },
  };

  return variants[variant] || variants.default;
}

export function getStatusVariant(theme, status) {
  const { colors } = theme;
  const variants = {
    active: { foreground: colors.success, background: colors.successSurface, label: "Active" },
    pending: { foreground: colors.warning, background: colors.warningSurface, label: "Pending" },
    completed: { foreground: colors.info, background: colors.infoSurface, label: "Completed" },
    warning: { foreground: colors.warning, background: colors.warningSurface, label: "Warning" },
    error: { foreground: colors.error, background: colors.errorSurface, label: "Error" },
    success: { foreground: colors.success, background: colors.successSurface, label: "Success" },
    info: { foreground: colors.info, background: colors.infoSurface, label: "Information" },
    neutral: { foreground: colors.textSecondary, background: colors.surfaceSecondary, label: "Status" },
  };

  return variants[status] || variants.neutral;
}
