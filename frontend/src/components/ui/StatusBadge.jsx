import { StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { getStatusVariant } from "../../theme/variants";

export function StatusBadge({ status = "neutral", label, icon, compact = false }) {
  const { theme, radius, typography } = useAppTheme();
  const statusStyle = getStatusVariant(theme, status);
  const visibleLabel = label || statusStyle.label;

  return (
    <View
      accessibilityRole="text"
      accessibilityLabel={`Status: ${visibleLabel}`}
      style={[
        styles.badge,
        {
          backgroundColor: statusStyle.background,
          borderRadius: radius.pill,
          paddingHorizontal: compact ? 9 : 12,
          paddingVertical: compact ? 5 : 7,
        },
      ]}
    >
      {icon ? <Text style={[styles.icon, { color: statusStyle.foreground }]}>{icon}</Text> : <View style={[styles.dot, { backgroundColor: statusStyle.foreground }]} />}
      <Text
        style={{
          color: statusStyle.foreground,
          fontSize: compact ? typography.sizes.caption : typography.sizes.small,
          fontWeight: typography.weights.bold,
        }}
      >
        {visibleLabel}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 7 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  icon: { fontSize: 12, fontWeight: "800" },
});
