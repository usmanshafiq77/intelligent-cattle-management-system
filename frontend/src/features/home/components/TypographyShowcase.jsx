import { StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../../theme/ThemeProvider";
import { ShowcaseSection } from "./ShowcaseSection";

export function TypographyShowcase() {
  const { theme, spacing, typography } = useAppTheme();

  return (
    <ShowcaseSection
      title="Typography and hierarchy"
      description="Shared type tokens keep headings, body copy, labels, and captions consistent across features."
      entranceDelay={90}
    >
      <View style={{ gap: spacing.sm }}>
        <Text style={[styles.display, { color: theme.colors.text, fontSize: typography.sizes.display, lineHeight: typography.lineHeights.display }]}>Farm overview</Text>
        <Text style={{ color: theme.colors.text, fontSize: typography.sizes.title, lineHeight: typography.lineHeights.title, fontWeight: typography.weights.bold }}>Healthy herds, informed decisions</Text>
        <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.body, lineHeight: typography.lineHeights.body }}>Readable content scales naturally while preserving a calm, professional visual rhythm.</Text>
        <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, lineHeight: typography.lineHeights.caption, fontWeight: typography.weights.bold, letterSpacing: typography.letterSpacing.eyebrow }}>SECTION LABEL</Text>
      </View>
    </ShowcaseSection>
  );
}

const styles = StyleSheet.create({ display: { fontWeight: "800" } });
