import { StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function NotFoundScreen({ onReturnHome }) {
  const { theme, spacing, typography, layout } = useAppTheme();

  return (
    <Screen style={[styles.screen, { backgroundColor: theme.colors.background }]}>
      <View style={[styles.content, { maxWidth: layout.formMaxWidth }]}>
        <Text style={[styles.code, { color: theme.colors.primary }]}>404</Text>
        <Text accessibilityRole="header" style={[styles.title, { color: theme.colors.text, fontSize: typography.sizes.heading, lineHeight: typography.lineHeights.heading }]}>Page not found</Text>
        <Text style={[styles.description, { color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body, marginTop: spacing.sm }]}>The requested ICMS page is unavailable.</Text>
        <AppButton title="Return to Welcome" onPress={onReturnHome} style={{ marginTop: spacing.xxl }} testID="not-found-home" />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: { alignItems: "center", justifyContent: "center", padding: 20 },
  content: { width: "100%", alignItems: "center" },
  code: { fontSize: 52, lineHeight: 60, fontWeight: "800", letterSpacing: 2 },
  title: { fontWeight: "800", textAlign: "center" },
  description: { textAlign: "center" },
});
