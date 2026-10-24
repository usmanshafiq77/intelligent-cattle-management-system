import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../../theme/ThemeProvider";

export function FarmSelector({ farms, activeFarmId, disabled, onSelect }) {
  const { theme, radius, spacing, typography } = useAppTheme();

  return (
    <View accessibilityRole="radiogroup" accessibilityLabel="Active farm" style={{ gap: spacing.sm }}>
      <Text style={{ color: theme.colors.text, fontSize: typography.sizes.small, fontWeight: typography.weights.bold }}>
        Active farm
      </Text>
      <View style={styles.options}>
        {farms.map((farm) => {
          const selected = farm.id === activeFarmId;
          return (
            <Pressable
              key={farm.id}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected, disabled }}
              accessibilityLabel={`Use ${farm.name}`}
              disabled={disabled}
              onPress={() => onSelect(farm.id)}
              testID={`farm-option-${farm.id}`}
              style={({ pressed }) => [
                styles.option,
                {
                  backgroundColor: selected ? theme.colors.primary : theme.colors.surface,
                  borderColor: selected ? theme.colors.primary : theme.colors.border,
                  borderRadius: radius.md,
                  opacity: disabled ? 0.55 : pressed ? 0.78 : 1,
                  paddingHorizontal: spacing.md,
                  paddingVertical: spacing.sm,
                },
              ]}
            >
              <Text numberOfLines={1} style={{ color: selected ? theme.colors.onPrimary : theme.colors.text, fontWeight: typography.weights.semibold }}>
                {farm.name}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  options: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  option: { minHeight: 44, minWidth: 120, justifyContent: "center", borderWidth: 1 },
});
