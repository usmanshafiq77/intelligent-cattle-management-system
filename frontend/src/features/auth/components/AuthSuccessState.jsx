import { StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function AuthSuccessState({ title, message, detail, primaryTitle, onPrimary, secondaryTitle, onSecondary, secondaryLoading = false, feedback }) {
  const { theme, spacing, radius, typography } = useAppTheme();
  return (
    <View accessibilityLiveRegion="polite" style={styles.container}>
      <View style={[styles.check, { backgroundColor: theme.colors.successSurface, borderRadius: radius.pill }]}>
        <Text style={[styles.checkText, { color: theme.colors.success }]}>✓</Text>
      </View>
      <Text accessibilityRole="header" style={[styles.title, { color: theme.colors.text, fontSize: typography.sizes.title, lineHeight: typography.lineHeights.title, marginTop: spacing.lg }]}>{title}</Text>
      <Text style={[styles.message, { color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body, marginTop: spacing.sm }]}>{message}</Text>
      {detail ? <Text style={[styles.detail, { color: theme.colors.textSecondary, marginTop: spacing.md }]}>{detail}</Text> : null}
      {feedback ? <View style={{ width: "100%", marginTop: spacing.lg }}><InlineFeedback type={feedback.type} message={feedback.message} /></View> : null}
      <View style={[styles.actions, { gap: spacing.md, marginTop: spacing.xxl }]}>
        <AppButton title={primaryTitle} onPress={onPrimary} />
        {secondaryTitle ? <AppButton title={secondaryTitle} variant="outline" onPress={onSecondary} loading={secondaryLoading} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center" },
  check: { width: 64, height: 64, alignItems: "center", justifyContent: "center" },
  checkText: { fontSize: 30, fontWeight: "800" },
  title: { fontWeight: "800", textAlign: "center" },
  message: { textAlign: "center", maxWidth: 430 },
  detail: { fontSize: 13, lineHeight: 19, textAlign: "center", maxWidth: 430 },
  actions: { width: "100%" },
});
