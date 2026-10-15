import { StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { getStatusVariant } from "../../theme/variants";
import { FadeInView } from "./FadeInView";

export function InlineFeedback({ type = "info", message }) {
  const { theme, radius, spacing, typography } = useAppTheme();
  const status = getStatusVariant(theme, type);
  const urgent = type === "error";

  if (!message) return null;

  return (
    <FadeInView distance={4}>
      <View
        accessibilityRole={urgent ? "alert" : undefined}
        accessibilityLiveRegion={urgent ? "assertive" : "polite"}
        style={[
          styles.container,
          {
            backgroundColor: status.background,
            borderColor: status.foreground,
            borderRadius: radius.md,
            padding: spacing.md,
          },
        ]}
      >
        <View style={[styles.marker, { backgroundColor: status.foreground }]} />
        <Text
          style={{
            color: status.foreground,
            flex: 1,
            fontSize: typography.sizes.small,
            lineHeight: typography.lineHeights.small,
            fontWeight: typography.weights.medium,
          }}
        >
          {message}
        </Text>
      </View>
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "row", alignItems: "flex-start", borderLeftWidth: 3, gap: 10 },
  marker: { width: 8, height: 8, borderRadius: 4, marginTop: 6 },
});
