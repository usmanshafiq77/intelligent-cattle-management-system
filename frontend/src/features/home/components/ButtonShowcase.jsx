import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ShowcaseSection } from "./ShowcaseSection";

export function ButtonShowcase() {
  const { theme, spacing, typography } = useAppTheme();
  const [message, setMessage] = useState("");

  return (
    <ShowcaseSection
      title="Buttons and action states"
      description="Theme-aware variants include accessible sizing, keyboard focus, reduced-motion support, and clear pending states."
      entranceDelay={120}
    >
      <View style={{ gap: spacing.md }}>
        <AppButton title="Primary action" onPress={() => setMessage("Primary preview action selected. No data was sent.")} />
        <AppButton title="Secondary action" variant="secondary" onPress={() => setMessage("Secondary preview action selected.")} />
        <AppButton title="Outline action" variant="outline" size="small" onPress={() => setMessage("Outline preview action selected.")} />
        <AppButton title="Danger action" variant="danger" onPress={() => setMessage("Danger preview selected. No record was changed.")} />
        <View style={styles.row}>
          <View style={styles.rowItem}><AppButton title="Loading" loading size="small" /></View>
          <View style={styles.rowItem}><AppButton title="Disabled" disabled variant="secondary" size="small" /></View>
        </View>
      </View>
      <InlineFeedback type="info" message={message} />
      <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.caption, lineHeight: typography.lineHeights.caption, marginTop: spacing.md }}>
        Preview controls only. Loading and disabled examples are intentionally inactive.
      </Text>
    </ShowcaseSection>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  rowItem: { flex: 1, minWidth: 140 },
});
