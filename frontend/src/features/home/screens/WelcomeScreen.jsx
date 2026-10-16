import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { FadeInView } from "../../../components/ui/FadeInView";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ButtonShowcase } from "../components/ButtonShowcase";
import { CardShowcase } from "../components/CardShowcase";
import { FeedbackShowcase } from "../components/FeedbackShowcase";
import { InputShowcase } from "../components/InputShowcase";
import { ThemeSelector } from "../components/ThemeSelector";
import { TypographyShowcase } from "../components/TypographyShowcase";

export function DesignSystemScreen() {
  const { width } = useWindowDimensions();
  const { theme, spacing, radius, typography, layout, themeRestoreError } = useAppTheme();
  const compact = width < layout.breakpoints.compact;
  const screenPadding = compact ? layout.compactScreenPadding : layout.screenPadding;

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.container,
          { paddingHorizontal: screenPadding, paddingVertical: compact ? spacing.xl : spacing.xxxl },
        ]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        showsVerticalScrollIndicator
      >
        <View style={[styles.content, { maxWidth: layout.contentMaxWidth, gap: spacing.xl }]}>
          <FadeInView distance={6}>
            <LinearGradient
              colors={theme.gradients.primary}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={[
                styles.hero,
                {
                  borderRadius: radius.xl,
                  padding: compact ? spacing.xl : spacing.xxxl,
                  minHeight: compact ? 220 : 250,
                },
              ]}
            >
              <Text style={[styles.heroEyebrow, { letterSpacing: typography.letterSpacing.eyebrow }]}>ICMS DEVELOPMENT PREVIEW</Text>
              <Text
                style={[
                  styles.heroTitle,
                  {
                    fontSize: compact ? typography.sizes.heading : typography.sizes.display,
                    lineHeight: compact ? typography.lineHeights.heading : typography.lineHeights.display,
                  },
                ]}
              >
                A premium foundation for smarter farm management
              </Text>
              <Text style={[styles.heroDescription, { fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body }]}>
                Step 19.2 demonstrates reusable styling, accessible controls, responsive layouts, and calm micro-interactions before production screens are introduced.
              </Text>
              <View style={[styles.heroBadge, { borderRadius: radius.pill }]}>
                <Text style={styles.heroBadgeText}>DESIGN SYSTEM - SAMPLE DATA ONLY</Text>
              </View>
            </LinearGradient>
          </FadeInView>

          {themeRestoreError ? (
            <InlineFeedback type="warning" message="The saved theme could not be restored, so Emerald Luxury is being used for this session." />
          ) : null}

          <ThemeSelector />
          <TypographyShowcase />
          <ButtonShowcase />
          <InputShowcase />
          <CardShowcase />
          <FeedbackShowcase />

          <Text
            style={{
              color: theme.colors.textSecondary,
              fontSize: typography.sizes.caption,
              lineHeight: typography.lineHeights.caption,
              textAlign: "center",
              marginTop: spacing.sm,
              marginBottom: spacing.lg,
            }}
          >
            ICMS Design System - Step 19.2 - Development showcase only
          </Text>
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  container: { flexGrow: 1, alignItems: "center", width: "100%" },
  content: { alignSelf: "center", minWidth: 0, width: "100%" },
  hero: { justifyContent: "center", overflow: "hidden" },
  heroEyebrow: { color: "#D9FFF2", fontSize: 11, fontWeight: "800" },
  heroTitle: { color: "#FFFFFF", fontWeight: "800", marginTop: 12, maxWidth: 760 },
  heroDescription: { color: "#F2FFF9", marginTop: 10, maxWidth: 720 },
  heroBadge: { alignSelf: "flex-start", backgroundColor: "rgba(255,255,255,0.18)", paddingHorizontal: 12, paddingVertical: 7, marginTop: 22 },
  heroBadgeText: { color: "#FFFFFF", fontSize: 10, fontWeight: "800", letterSpacing: 0.7 },
});
