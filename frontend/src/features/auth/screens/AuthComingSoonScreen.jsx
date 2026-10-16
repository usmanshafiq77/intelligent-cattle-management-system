import { StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { BrandMark } from "../../../components/brand/BrandMark";
import { AppButton } from "../../../components/ui/AppButton";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function AuthComingSoonScreen({ journey, onBack }) {
  const { theme, spacing, radius, typography, shadows } = useAppTheme();
  const isSignup = journey === "signup";
  const title = isSignup ? "Create your ICMS account" : "Welcome back";
  const description = isSignup
    ? "Account creation arrives in Step 19.5. No information is collected on this preview screen."
    : "Secure login arrives in Step 19.5. This preview does not accept credentials or create a session.";

  return (
    <Screen style={[styles.screen, { backgroundColor: theme.colors.background }]}>
      <LinearGradient colors={theme.gradients.background} style={StyleSheet.absoluteFillObject} />
      <View style={[styles.card, shadows.large, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: spacing.xxl }]}>
        <BrandMark size={64} />
        <Text accessibilityRole="header" style={[styles.title, { color: theme.colors.text, fontSize: typography.sizes.heading, lineHeight: typography.lineHeights.heading, marginTop: spacing.xl }]}>
          {title}
        </Text>
        <View style={[styles.badge, { backgroundColor: theme.colors.infoSurface, borderRadius: radius.pill, marginTop: spacing.md }]}>
          <Text style={[styles.badgeText, { color: theme.colors.info }]}>COMING IN STEP 19.5</Text>
        </View>
        <Text style={[styles.description, { color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body, marginTop: spacing.lg }]}>
          {description}
        </Text>
        <AppButton
          title="Back to Welcome"
          variant="outline"
          onPress={onBack}
          accessibilityHint="Returns to the ICMS welcome screen"
          style={{ marginTop: spacing.xxl }}
          testID="auth-placeholder-back"
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: { alignItems: "center", justifyContent: "center", padding: 20 },
  card: { width: "100%", maxWidth: 500, borderWidth: 1, alignItems: "center" },
  title: { fontWeight: "800", textAlign: "center" },
  badge: { paddingHorizontal: 12, paddingVertical: 7 },
  badgeText: { fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  description: { textAlign: "center", maxWidth: 400 },
});
