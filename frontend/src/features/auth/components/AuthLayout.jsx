import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { BrandMark } from "../../../components/brand/BrandMark";
import { FadeInView } from "../../../components/ui/FadeInView";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function AuthLayout({ eyebrow, title, subtitle, onBack, children }) {
  const { width } = useWindowDimensions();
  const { theme, spacing, radius, shadows, typography, layout } = useAppTheme();
  const compact = width < layout.breakpoints.compact;
  const [backFocused, setBackFocused] = useState(false);

  return (
    <Screen avoidKeyboard={false} safeEdges={["right", "bottom", "left"]} style={{ backgroundColor: theme.colors.background }}>
      <LinearGradient colors={theme.gradients.background} style={StyleSheet.absoluteFillObject} />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          contentContainerStyle={[
            styles.scrollContent,
            { paddingHorizontal: compact ? layout.compactScreenPadding : layout.screenPadding, paddingVertical: spacing.xl },
          ]}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          showsVerticalScrollIndicator={false}
        >
          <View style={[styles.shell, { maxWidth: layout.formMaxWidth }]}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Back to welcome"
              onPress={onBack}
              onFocus={() => setBackFocused(true)}
              onBlur={() => setBackFocused(false)}
              style={({ pressed }) => [
                styles.back,
                { opacity: pressed ? 0.65 : 1, minHeight: layout.minTouchTarget },
                backFocused && styles.backFocused,
                backFocused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: { borderColor: theme.colors.focusRing } }),
              ]}
            >
              <Text style={[styles.backText, { color: theme.colors.primary }]}>← Back</Text>
            </Pressable>

            <FadeInView distance={8} style={styles.brand}>
              <BrandMark size={58} showWordmark />
            </FadeInView>

            <FadeInView delay={40} distance={10}>
              <Text style={[styles.eyebrow, { color: theme.colors.primary, letterSpacing: typography.letterSpacing.eyebrow }]}>{eyebrow}</Text>
              <Text accessibilityRole="header" style={[styles.title, { color: theme.colors.text, fontSize: compact ? typography.sizes.heading : typography.sizes.display, lineHeight: compact ? typography.lineHeights.heading : typography.lineHeights.display }]}>
                {title}
              </Text>
              <Text style={[styles.subtitle, { color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body }]}>{subtitle}</Text>
            </FadeInView>

            <FadeInView
              delay={80}
              distance={10}
              style={[
                styles.card,
                shadows.large,
                { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: compact ? spacing.lg : spacing.xxl },
              ]}
            >
              {children}
            </FadeInView>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scrollContent: { flexGrow: 1, alignItems: "center", justifyContent: "center" },
  shell: { width: "100%" },
  back: { alignSelf: "flex-start", justifyContent: "center", paddingHorizontal: 4, marginBottom: 8 },
  backFocused: Platform.select({
    web: { outlineStyle: "solid", outlineWidth: 2, outlineOffset: 2 },
    default: { borderWidth: 2 },
  }),
  backText: { fontSize: 14, fontWeight: "700" },
  brand: { alignSelf: "flex-start", marginBottom: 26 },
  eyebrow: { fontSize: 11, fontWeight: "800", marginBottom: 7 },
  title: { fontWeight: "800", letterSpacing: -0.5 },
  subtitle: { marginTop: 9, maxWidth: 520 },
  card: { width: "100%", borderWidth: 1, marginTop: 26 },
});
