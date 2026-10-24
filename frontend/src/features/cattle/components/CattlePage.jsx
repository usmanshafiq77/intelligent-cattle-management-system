import { ScrollView, StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function CattlePage({ eyebrow = "HERD MANAGEMENT", title, subtitle, onBack, action, children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return (
    <View style={[styles.screen, { backgroundColor: theme.colors.background }]}>
      <ScrollView contentContainerStyle={[styles.content, { maxWidth: layout.contentMaxWidth, padding: spacing.xl }]} keyboardShouldPersistTaps="handled">
        <View style={styles.topRow}>
          <AppButton title="Back" variant="outline" size="small" fullWidth={false} onPress={onBack} accessibilityLabel="Back to cattle dashboard" />
          {action || null}
        </View>
        <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold, letterSpacing: typography.letterSpacing.eyebrow, marginTop: spacing.xl }}>{eyebrow}</Text>
        <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, lineHeight: typography.lineHeights.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.xs }}>{title}</Text>
        {subtitle ? <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body, marginTop: spacing.sm, marginBottom: spacing.xxl }}>{subtitle}</Text> : <View style={{ height: spacing.xxl }} />}
        {children}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { width: "100%", alignSelf: "center", paddingBottom: 56 },
  topRow: { minHeight: 44, flexDirection: "row", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 },
});
