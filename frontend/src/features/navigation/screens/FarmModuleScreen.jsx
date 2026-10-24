import { ScrollView, StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { moduleForRoute } from "../../permissions/navigationConfig";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function FarmModuleScreen({ moduleKey, onBack }) {
  const module = moduleForRoute(moduleKey);
  const farm = useFarm();
  const { theme, spacing, typography, layout } = useAppTheme();

  if (!module) {
    return (
      <Screen style={[styles.center, { backgroundColor: theme.colors.background, padding: spacing.xl }]}>
        <FeedbackState type="error" title="Unknown module" message="This route is not part of the reviewed ICMS navigation configuration." actionLabel="Return to dashboard" onAction={onBack} />
      </Screen>
    );
  }

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <RequireFarm>
        <RequirePermission permission={module.permission}>
          <ScrollView contentContainerStyle={[styles.content, { maxWidth: layout.formMaxWidth, padding: spacing.xl }]}>
            <AppCard>
              <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold }}>VERIFIED FARM MODULE</Text>
              <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.sm }}>{module.title}</Text>
              <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>{farm.activeFarm?.name}</Text>
              <Text style={{ color: theme.colors.text, marginTop: spacing.xl }}>Your backend permission for this module is confirmed. The operational screen is intentionally reserved for a later implementation step.</Text>
              <AppButton title="Return to dashboard" onPress={onBack} style={{ marginTop: spacing.xl }} />
            </AppCard>
          </ScrollView>
        </RequirePermission>
      </RequireFarm>
    </Screen>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: "center" },
  content: { width: "100%", alignSelf: "center", justifyContent: "center", flexGrow: 1 },
});
