import { StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { AppCard } from "./AppCard";
import { StatusBadge } from "./StatusBadge";

export function StatCard({
  label,
  value,
  unit,
  caption,
  icon,
  status,
  statusLabel,
  sample = false,
  entranceDelay = 0,
  style,
}) {
  const { theme, spacing, typography } = useAppTheme();

  return (
    <AppCard variant="highlight" icon={icon} entranceDelay={entranceDelay} compact style={style}>
      <View style={styles.labelRow}>
        <Text
          style={{
            color: theme.colors.textSecondary,
            fontSize: typography.sizes.small,
            lineHeight: typography.lineHeights.small,
            flex: 1,
          }}
        >
          {label}
        </Text>
        {status ? <StatusBadge status={status} label={statusLabel} compact /> : null}
      </View>
      <View style={[styles.valueRow, { marginTop: spacing.sm }]}>
        <Text
          style={{
            color: theme.colors.primary,
            fontSize: typography.sizes.heading,
            lineHeight: typography.lineHeights.heading,
            fontWeight: typography.weights.extrabold,
          }}
        >
          {value}
        </Text>
        {unit ? (
          <Text
            style={{
              color: theme.colors.textSecondary,
              fontSize: typography.sizes.small,
              marginBottom: 4,
              marginLeft: spacing.xs,
            }}
          >
            {unit}
          </Text>
        ) : null}
      </View>
      {caption || sample ? (
        <Text
          style={{
            color: theme.colors.textSecondary,
            fontSize: typography.sizes.caption,
            lineHeight: typography.lineHeights.caption,
            marginTop: spacing.xs,
          }}
        >
          {caption}
          {caption && sample ? " - " : ""}
          {sample ? "Sample data" : ""}
        </Text>
      ) : null}
    </AppCard>
  );
}

const styles = StyleSheet.create({
  labelRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  valueRow: { flexDirection: "row", alignItems: "flex-end" },
});
