import { ScrollView, StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { roleLabel } from "../../permissions/permissionCatalog";
import { FarmSelector } from "../components/FarmSelector";
import { useFarm } from "../context/FarmProvider";

export function FarmSelectionScreen({ onBack, onCreate }) {
  const farm = useFarm();
  const { theme, spacing, typography, layout } = useAppTheme();
  const select = (farmId) => { void farm.selectFarm(farmId); };

  let body;
  if (farm.isLoading || farm.status === "creating") {
    body = <FeedbackState type="loading" title="Loading your farms" message="Verifying accessible farms and the selected farm permissions." showSkeleton />;
  } else if (farm.status === "no-farms") {
    body = <FeedbackState title="Create your first farm" message="No active farm membership is available for this account yet." actionLabel="Create Farm" onAction={onCreate} />;
  } else if (farm.status === "unavailable" || farm.status === "permission-unavailable") {
    body = <FeedbackState type="error" title="Farm list unavailable" message={farm.issue?.message} actionLabel="Retry" onAction={() => { void farm.refreshFarms(); }} />;
  } else {
    body = (
      <View style={{ gap: spacing.lg }}>
        <FarmSelector farms={farm.farms} activeFarmId={farm.activeFarm?.id} disabled={farm.isLoading} onSelect={select} />
        {farm.activeFarm ? (
          <AppCard>
            <Text style={{ color: theme.colors.text, fontSize: typography.sizes.subtitle, fontWeight: typography.weights.bold }}>{farm.activeFarm.name}</Text>
            <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{roleLabel(farm.membership?.role)} · verified active membership</Text>
          </AppCard>
        ) : <Text style={{ color: theme.colors.textSecondary }}>Choose a farm to verify its current role and effective permissions.</Text>}
      </View>
    );
  }

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <ScrollView contentContainerStyle={[styles.content, { maxWidth: layout.formMaxWidth, padding: spacing.xl }]}>
        <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold }}>FARM CONTEXT</Text>
        <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.xs }}>Select a farm</Text>
        <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm, marginBottom: spacing.xl }}>Only farms returned by the server as active memberships can be selected.</Text>
        {body}
        <View style={{ gap: spacing.md, marginTop: spacing.xl }}>
          {farm.farms.length ? <AppButton title="Create another farm" variant="outline" onPress={onCreate} /> : null}
          <AppButton title="Refresh farm list" variant="outline" onPress={() => { void farm.refreshFarms(); }} loading={farm.isLoading} />
          <AppButton title="Back to dashboard" variant="outline" onPress={onBack} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({ content: { width: "100%", alignSelf: "center", paddingBottom: 48 } });
