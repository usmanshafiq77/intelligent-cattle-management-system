import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useState } from "react";

import { useAppTheme } from "../../../theme/ThemeProvider";

export function AuthSwitchPrompt({ message, action, onPress }) {
  const { theme, layout } = useAppTheme();
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.row}>
      <Text style={[styles.message, { color: theme.colors.textSecondary }]}>{message}</Text>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={action}
        onPress={onPress}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={({ pressed }) => [
          styles.link,
          { minHeight: layout.minTouchTarget, opacity: pressed ? 0.65 : 1 },
          focused && styles.focused,
          focused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: { borderColor: theme.colors.focusRing } }),
        ]}
      >
        <Text style={[styles.action, { color: theme.colors.primary }]}>{action}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "center", gap: 4 },
  message: { fontSize: 14 },
  link: { justifyContent: "center", paddingHorizontal: 5, borderRadius: 6 },
  focused: Platform.select({
    web: { outlineStyle: "solid", outlineWidth: 2, outlineOffset: 2 },
    default: { borderWidth: 2 },
  }),
  action: { fontSize: 14, fontWeight: "800" },
});
