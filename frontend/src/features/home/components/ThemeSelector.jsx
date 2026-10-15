import { useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { THEME_IDS } from "../../../theme/themes";
import { ShowcaseSection } from "./ShowcaseSection";

export function ThemeSelector() {
  const { theme, themeId, themes, changeTheme, spacing, radius, typography } = useAppTheme();
  const [switching, setSwitching] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [focusedTheme, setFocusedTheme] = useState(null);

  const selectTheme = async (id) => {
    if (switching || id === themeId) return;
    setSwitching(true);
    setErrorMessage("");
    try {
      await changeTheme(id);
    } catch {
      setErrorMessage("Unable to save the theme preference. The previous theme was restored.");
    } finally {
      setSwitching(false);
    }
  };

  return (
    <ShowcaseSection
      title="Choose your theme"
      description="The selected premium palette updates every theme-aware component and persists on this device."
      entranceDelay={60}
    >
      <View style={[styles.options, { gap: spacing.md }]} accessibilityRole="radiogroup">
        {THEME_IDS.map((id) => {
          const option = themes[id];
          const selected = id === themeId;
          const focused = id === focusedTheme;

          return (
            <Pressable
              key={id}
              disabled={switching}
              onPress={() => selectTheme(id)}
              onFocus={() => setFocusedTheme(id)}
              onBlur={() => setFocusedTheme(null)}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected, disabled: switching }}
              accessibilityLabel={`${option.name} theme`}
              style={[
                styles.option,
                {
                  backgroundColor: selected ? theme.colors.surfaceSecondary : theme.colors.surface,
                  borderColor: selected || focused ? theme.colors.focusRing : theme.colors.border,
                  borderWidth: selected || focused ? 2 : 1,
                  borderRadius: radius.lg,
                  opacity: switching && !selected ? 0.65 : 1,
                },
                focused && styles.webFocus,
                focused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: {} }),
              ]}
            >
              <LinearGradient
                colors={option.gradients.primary}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={[styles.swatch, { borderRadius: radius.md }]}
              />
              <View style={styles.optionInfo}>
                <Text
                  style={{
                    color: theme.colors.text,
                    fontSize: typography.sizes.body,
                    fontWeight: typography.weights.bold,
                  }}
                >
                  {option.name}
                </Text>
                <Text style={[styles.optionSubtitle, { color: theme.colors.textSecondary }]}>
                  {selected ? "Currently selected" : "Select palette"}
                </Text>
              </View>
              <View
                style={[
                  styles.radio,
                  {
                    borderColor: selected ? theme.colors.primary : theme.colors.border,
                    backgroundColor: selected ? theme.colors.primary : "transparent",
                  },
                ]}
              >
                {selected ? <View style={styles.radioCenter} /> : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      {switching ? (
        <View style={[styles.saving, { marginTop: spacing.md }]} accessibilityLiveRegion="polite">
          <ActivityIndicator color={theme.colors.primary} />
          <Text style={{ color: theme.colors.textSecondary }}>Saving appearance</Text>
        </View>
      ) : null}
      <InlineFeedback type="error" message={errorMessage} />
    </ShowcaseSection>
  );
}

const styles = StyleSheet.create({
  options: { width: "100%" },
  option: { minHeight: 76, flexDirection: "row", alignItems: "center", padding: 10, gap: 12 },
  swatch: { width: 50, height: 50 },
  optionInfo: { flex: 1, minWidth: 0 },
  optionSubtitle: { fontSize: 12, lineHeight: 17, marginTop: 3 },
  radio: { width: 24, height: 24, borderWidth: 2, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  radioCenter: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#FFFFFF" },
  saving: { flexDirection: "row", alignItems: "center", gap: 10 },
  webFocus: Platform.select({ web: { outlineStyle: "solid", outlineWidth: 2, outlineOffset: 2 }, default: {} }),
});
