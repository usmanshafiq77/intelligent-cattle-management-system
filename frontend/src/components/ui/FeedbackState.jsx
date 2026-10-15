import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { AppButton } from "./AppButton";
import { FadeInView } from "./FadeInView";
import { Skeleton } from "./Skeleton";

const DEFAULTS = {
  loading: { icon: "...", title: "Loading", message: "Please wait while the latest information is prepared." },
  empty: { icon: "0", title: "Nothing here yet", message: "New records will appear here when they are available." },
  error: { icon: "!", title: "Something went wrong", message: "Please try again when you are ready." },
  success: { icon: "OK", title: "Completed", message: "The action completed successfully." },
};

export function FeedbackState({
  type = "empty",
  title,
  message,
  actionLabel,
  onAction,
  compact = false,
  showSkeleton = false,
}) {
  const { theme, radius, spacing, typography } = useAppTheme();
  const content = DEFAULTS[type] || DEFAULTS.empty;
  const isLoading = type === "loading";
  const isError = type === "error";
  const isSuccess = type === "success";
  const tone = isError ? theme.colors.error : isSuccess ? theme.colors.success : theme.colors.primary;
  const surface = isError
    ? theme.colors.errorSurface
    : isSuccess
      ? theme.colors.successSurface
      : theme.colors.surfaceSecondary;

  return (
    <FadeInView>
      <View
        accessibilityRole={isError ? "alert" : undefined}
        accessibilityLiveRegion={isLoading ? "polite" : isError ? "assertive" : "polite"}
        accessibilityLabel={`${title || content.title}. ${message || content.message}`}
        style={[
          styles.container,
          {
            backgroundColor: surface,
            borderColor: theme.colors.border,
            borderRadius: radius.lg,
            padding: compact ? spacing.lg : spacing.xxl,
          },
        ]}
      >
        {isLoading ? (
          <ActivityIndicator size={compact ? "small" : "large"} color={tone} />
        ) : (
          <View style={[styles.icon, { backgroundColor: theme.colors.surface, borderRadius: radius.pill }]}>
            <Text style={{ color: tone, fontWeight: typography.weights.extrabold }}>{content.icon}</Text>
          </View>
        )}
        <Text
          style={{
            color: theme.colors.text,
            fontSize: compact ? typography.sizes.body : typography.sizes.subtitle,
            fontWeight: typography.weights.bold,
            marginTop: spacing.md,
            textAlign: "center",
          }}
        >
          {title || content.title}
        </Text>
        <Text
          style={{
            color: theme.colors.textSecondary,
            fontSize: typography.sizes.small,
            lineHeight: typography.lineHeights.small,
            marginTop: spacing.xs,
            maxWidth: 440,
            textAlign: "center",
          }}
        >
          {message || content.message}
        </Text>
        {showSkeleton && isLoading ? <Skeleton lines={3} style={{ marginTop: spacing.lg }} /> : null}
        {actionLabel && onAction ? (
          <AppButton
            title={actionLabel}
            onPress={onAction}
            variant={isError ? "outline" : "secondary"}
            size="small"
            fullWidth={false}
            style={{ marginTop: spacing.lg }}
          />
        ) : null}
      </View>
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  container: { width: "100%", borderWidth: 1, alignItems: "center" },
  icon: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
});
