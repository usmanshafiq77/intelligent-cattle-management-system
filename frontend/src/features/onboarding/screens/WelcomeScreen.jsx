import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";

import { BrandMark } from "../../../components/brand/BrandMark";
import { FarmIntelligenceGraphic } from "../../../components/brand/FarmIntelligenceGraphic";
import { AppButton } from "../../../components/ui/AppButton";
import { FadeInView } from "../../../components/ui/FadeInView";
import { Screen } from "../../../components/ui/Screen";
import { ROUTES } from "../../../navigation/routes";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function WelcomeScreen({ onGetStarted, onLogIn }) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { theme, spacing, typography, layout } = useAppTheme();
  const compact = width < layout.breakpoints.compact;
  const wide = width >= layout.breakpoints.tablet;
  const navigateToSignup = onGetStarted || (() => router.push(ROUTES.signup));
  const navigateToLogin = onLogIn || (() => router.push(ROUTES.login));

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <LinearGradient colors={theme.gradients.background} style={StyleSheet.absoluteFillObject} />
      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          {
            paddingHorizontal: compact ? layout.compactScreenPadding : layout.screenPadding,
            paddingVertical: compact ? spacing.lg : spacing.xxxl,
          },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}>
          <FadeInView distance={6} style={styles.header}>
            <BrandMark size={compact ? 52 : 60} showWordmark />
            <View style={[styles.statusPill, { backgroundColor: theme.colors.successSurface }]}>
              <View style={[styles.statusDot, { backgroundColor: theme.colors.success }]} />
              <Text style={[styles.statusText, { color: theme.colors.success }]}>SMART FARMING</Text>
            </View>
          </FadeInView>

          <View style={[styles.hero, wide && styles.heroWide, { gap: wide ? spacing.section : spacing.xxxl }]}>
            <View style={[styles.copy, wide && styles.copyWide]}>
              <FadeInView delay={40} distance={10}>
                <Text
                  accessibilityRole="header"
                  style={[
                    styles.headline,
                    {
                      color: theme.colors.text,
                      fontSize: wide ? 48 : compact ? typography.sizes.heading : typography.sizes.display,
                      lineHeight: wide ? 56 : compact ? typography.lineHeights.heading : typography.lineHeights.display,
                    },
                  ]}
                >
                  Smarter Farming{`\n`}
                  <Text style={{ color: theme.colors.primary }}>Starts Here</Text>
                </Text>
                <Text
                  style={[
                    styles.description,
                    {
                      color: theme.colors.textSecondary,
                      fontSize: typography.sizes.body,
                      lineHeight: typography.lineHeights.body,
                      marginTop: spacing.lg,
                    },
                  ]}
                >
                  Manage your cattle, monitor farm activities, and make better decisions with one intelligent platform.
                </Text>
              </FadeInView>

              <FadeInView delay={100} distance={8} style={[styles.actions, { gap: spacing.md, marginTop: spacing.xxl }]}>
                <AppButton
                  title="Get Started"
                  size="large"
                  onPress={navigateToSignup}
                  accessibilityHint="Opens the account setup introduction"
                  testID="welcome-get-started"
                />
                <AppButton
                  title="Log In"
                  size="large"
                  variant="outline"
                  onPress={navigateToLogin}
                  accessibilityHint="Opens the login introduction"
                  testID="welcome-log-in"
                />
              </FadeInView>

              <FadeInView delay={140} distance={6} style={[styles.trustRow, { marginTop: spacing.xl }]}>
                <Text style={[styles.trustText, { color: theme.colors.textSecondary }]}>Cattle</Text>
                <View style={[styles.separator, { backgroundColor: theme.colors.border }]} />
                <Text style={[styles.trustText, { color: theme.colors.textSecondary }]}>Health</Text>
                <View style={[styles.separator, { backgroundColor: theme.colors.border }]} />
                <Text style={[styles.trustText, { color: theme.colors.textSecondary }]}>Milk</Text>
              </FadeInView>
            </View>

            <FadeInView delay={70} distance={14} style={styles.graphicColumn}>
              <FarmIntelligenceGraphic />
            </FadeInView>
          </View>

          <Text style={[styles.footer, { color: theme.colors.textSecondary, marginTop: spacing.xxxl }]}>Built for calm, confident farm decisions.</Text>
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scrollContent: { flexGrow: 1, alignItems: "center" },
  shell: { width: "100%", flex: 1 },
  header: { width: "100%", flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statusPill: { minHeight: 32, paddingHorizontal: 11, borderRadius: 999, flexDirection: "row", alignItems: "center", gap: 6 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusText: { fontSize: 9, fontWeight: "800", letterSpacing: 0.8 },
  hero: { flex: 1, justifyContent: "center", paddingVertical: 30 },
  heroWide: { flexDirection: "row", alignItems: "center", paddingVertical: 54 },
  copy: { width: "100%", alignSelf: "center", maxWidth: 570 },
  copyWide: { flex: 1, alignSelf: "auto" },
  headline: { fontWeight: "800", letterSpacing: -0.8 },
  description: { maxWidth: 525 },
  actions: { width: "100%", maxWidth: 430 },
  trustRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  trustText: { fontSize: 12, fontWeight: "700", letterSpacing: 0.4 },
  separator: { width: 1, height: 14 },
  graphicColumn: { width: "100%", maxWidth: 460, alignSelf: "center" },
  footer: { textAlign: "center", fontSize: 12, lineHeight: 18 },
});
