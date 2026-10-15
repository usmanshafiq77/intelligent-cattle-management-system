import { StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { AppCard } from "../../../components/ui/AppCard";
import { StatCard } from "../../../components/ui/StatCard";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ShowcaseSection } from "./ShowcaseSection";

export function CardShowcase() {
  const { width } = useWindowDimensions();
  const { theme, spacing, typography, layout } = useAppTheme();
  const multiColumn = width >= layout.breakpoints.tablet;

  return (
    <ShowcaseSection
      title="Cards and status indicators"
      description="Reusable variants support dashboards, cattle summaries, milk insights, health states, and contextual actions."
      entranceDelay={180}
    >
      <View style={[styles.grid, { gap: spacing.md }]}>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <StatCard label="Today's milk" value="125.5" unit="L" caption="Across 14 sessions" icon="M" status="active" sample entranceDelay={40} />
        </View>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <StatCard label="Healthy cattle" value="24" unit="head" caption="Two reviews pending" icon="C" status="pending" sample entranceDelay={80} />
        </View>
      </View>
      <View style={{ marginTop: spacing.md }}>
        <AppCard
          overline="SAMPLE CATTLE PROFILE"
          title="ICMS-024 - Holstein"
          subtitle="Female | Lactating | Barn A"
          icon="C"
          variant="outlined"
          entranceDelay={120}
        >
          <View style={[styles.badges, { gap: spacing.sm }]}>
            <StatusBadge status="active" label="Active" />
            <StatusBadge status="completed" label="Vaccinated" />
            <StatusBadge status="warning" label="Review due" />
          </View>
          <Text
            style={{
              color: theme.colors.textSecondary,
              fontSize: typography.sizes.caption,
              lineHeight: typography.lineHeights.caption,
              marginTop: spacing.md,
            }}
          >
            Sample data for component demonstration only.
          </Text>
        </AppCard>
      </View>
      <View style={[styles.badges, { gap: spacing.sm, marginTop: spacing.lg }]} accessibilityLabel="Available status badge variants">
        <StatusBadge status="active" />
        <StatusBadge status="pending" />
        <StatusBadge status="completed" />
        <StatusBadge status="warning" />
        <StatusBadge status="error" />
      </View>
    </ShowcaseSection>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap" },
  gridItem: { flexGrow: 1, flexBasis: "46%", minWidth: 260 },
  fullItem: { width: "100%" },
  badges: { flexDirection: "row", flexWrap: "wrap", alignItems: "center" },
});
