import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../../theme/ThemeProvider";
import { optionLabel } from "../cattleOptions";

export function OptionField({ label, value, options, onChange, error, required = false, disabled = false, testID }) {
  const { theme, radius, spacing, typography } = useAppTheme();
  return (
    <View style={{ gap: spacing.sm }}>
      <Text style={{ color: theme.colors.text, fontSize: typography.sizes.small, fontWeight: typography.weights.semibold }}>
        {label}{required ? <Text style={{ color: theme.colors.error }}> *</Text> : null}
      </Text>
      <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.options}>
        {options.map((option) => {
          const selected = value === option;
          return (
            <Pressable
              key={option}
              testID={testID ? `${testID}-${option}` : undefined}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected, disabled }}
              disabled={disabled}
              onPress={() => onChange(option)}
              style={({ pressed }) => ({
                minHeight: 44,
                justifyContent: "center",
                paddingHorizontal: spacing.md,
                borderWidth: 1,
                borderColor: error ? theme.colors.error : selected ? theme.colors.primary : theme.colors.border,
                backgroundColor: selected ? theme.colors.surfaceSecondary : theme.colors.surface,
                borderRadius: radius.md,
                opacity: disabled ? 0.55 : pressed ? 0.72 : 1,
              })}
            >
              <Text style={{ color: selected ? theme.colors.primary : theme.colors.text, fontWeight: typography.weights.semibold }}>{option === "" ? "All" : optionLabel(option)}</Text>
            </Pressable>
          );
        })}
      </View>
      {error ? <Text accessibilityRole="alert" style={{ color: theme.colors.error, fontSize: typography.sizes.caption }}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({ options: { flexDirection: "row", flexWrap: "wrap", gap: 8 } });
