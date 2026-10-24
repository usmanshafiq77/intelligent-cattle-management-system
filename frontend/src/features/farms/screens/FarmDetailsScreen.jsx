import { useEffect, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { farmsApi } from "../../../api/farms";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { roleLabel } from "../../permissions/permissionCatalog";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { useFarm } from "../context/FarmProvider";
import { farmErrorMessage } from "../farmErrors";
import { requireFarmResponse } from "../farmContracts";

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleDateString();
}

function DetailsContent({ api, onBack }) {
  const farm = useFarm();
  const { theme, spacing, typography, layout } = useAppTheme();
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const requestId = useRef(0);

  const load = () => {
    const id = ++requestId.current;
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });
    api.get(farm.activeFarm.id, { signal: controller.signal })
      .then((payload) => {
        const details = requireFarmResponse(payload);
        if (details.id !== farm.activeFarm.id) throw new Error("The farm details response did not match the selected farm.");
        if (requestId.current === id) setState({ status: "ready", data: details, error: null });
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.isCancelled || requestId.current !== id) return;
        setState({ status: "error", data: null, error });
      });
    return () => controller.abort();
  };

  useEffect(() => load(), [farm.activeFarm.id]);

  if (state.status === "loading") return <FeedbackState type="loading" title="Loading farm details" message="Confirming the selected farm with the server." showSkeleton />;
  if (state.status === "error") return <FeedbackState type="error" title="Farm details unavailable" message={farmErrorMessage(state.error)} actionLabel="Retry" onAction={load} />;

  const details = state.data;
  return (
    <ScrollView contentContainerStyle={[styles.content, { maxWidth: layout.formMaxWidth, padding: spacing.xl }]}>
      <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold }}>FARM OVERVIEW</Text>
      <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.xs }}>{details.name}</Text>
      <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>Read-only details confirmed by the current farm endpoint.</Text>
      <AppCard style={{ marginTop: spacing.xl }}>
        <View style={{ gap: spacing.lg }}>
          <Detail label="Location" value={details.location || "Not provided"} />
          <Detail label="Description" value={details.description || "Not provided"} />
          <Detail label="Created" value={formatDate(details.created_at)} />
          <Detail label="Current membership" value={`${roleLabel(farm.membership?.role)} · ${farm.membership?.status || "ACTIVE"}`} />
          <Detail label="Farm identifier" value={details.id} mono />
          <Detail label="Owner identifier" value={details.owner_id} mono />
        </View>
      </AppCard>
      <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.lg }}>Editing and deletion are unavailable because the reviewed backend exposes no farm update or delete endpoint.</Text>
      <AppButton title="Back to dashboard" onPress={onBack} style={{ marginTop: spacing.xl }} />
    </ScrollView>
  );
}

function Detail({ label, value, mono = false }) {
  const { theme, typography } = useAppTheme();
  return (
    <View>
      <Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.caption, fontWeight: typography.weights.bold }}>{label}</Text>
      <Text selectable={mono} style={{ color: theme.colors.text, marginTop: 3, fontFamily: mono ? "monospace" : undefined }}>{value}</Text>
    </View>
  );
}

export function FarmDetailsScreen({ onBack, api = farmsApi }) {
  const { theme } = useAppTheme();
  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <RequireFarm>
        <RequirePermission permission="farm.view">
          <DetailsContent api={api} onBack={onBack} />
        </RequirePermission>
      </RequireFarm>
    </Screen>
  );
}

const styles = StyleSheet.create({ content: { width: "100%", alignSelf: "center", paddingBottom: 48 } });
