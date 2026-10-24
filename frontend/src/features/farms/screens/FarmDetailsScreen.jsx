import { useEffect, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { farmsApi } from "../../../api/farms";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { roleLabel } from "../../permissions/permissionCatalog";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { useFarm } from "../context/FarmProvider";
import { farmErrorMessage } from "../farmErrors";
import { requireFarmResponse } from "../farmContracts";
import { farmPayload, validateFarm } from "../farmValidation";

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleDateString();
}

function DetailsContent({ api, onBack }) {
  const farm = useFarm();
  const { theme, spacing, typography, layout } = useAppTheme();
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [values, setValues] = useState({ name: "", location: "", description: "" });
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const requestId = useRef(0);

  const load = () => {
    const id = ++requestId.current;
    const controller = new AbortController();
    setState({ status: "loading", data: null, error: null });
    api.get(farm.activeFarm.id, { signal: controller.signal })
      .then((payload) => {
        const details = requireFarmResponse(payload);
        if (details.id !== farm.activeFarm.id) throw new Error("The farm details response did not match the selected farm.");
        if (requestId.current === id) {
          setState({ status: "ready", data: details, error: null });
          setValues({ name: details.name, location: details.location || "", description: details.description || "" });
        }
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
  const submit = async () => {
    const nextErrors = validateFarm(values);
    setErrors(nextErrors);
    setFeedback(null);
    if (Object.keys(nextErrors).length) return;
    setSaving(true);
    try {
      const updated = requireFarmResponse(await api.update(details.id, farmPayload(values)));
      if (updated.id !== details.id) throw new Error("The farm update response did not match the selected farm.");
      setState({ status: "ready", data: updated, error: null });
      setValues({ name: updated.name, location: updated.location || "", description: updated.description || "" });
      setEditing(false);
      setFeedback({ type: "success", message: "Farm profile updated." });
      await farm.refreshFarms();
    } catch (error) {
      setFeedback({ type: "error", message: farmErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  };
  return (
    <ScrollView contentContainerStyle={[styles.content, { maxWidth: layout.formMaxWidth, padding: spacing.xl }]}>
      <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold }}>FARM OVERVIEW</Text>
      <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.xs }}>{details.name}</Text>
      <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>Read-only details confirmed by the current farm endpoint.</Text>
      <AppCard style={{ marginTop: spacing.xl }}>
        {editing ? <View style={{ gap: spacing.lg }}>
          <AppInput label="Farm name" value={values.name} onChangeText={(name) => setValues((current) => ({ ...current, name }))} error={errors.name} testID="farm-edit-name" required />
          <AppInput label="Location" value={values.location} onChangeText={(location) => setValues((current) => ({ ...current, location }))} error={errors.location} testID="farm-edit-location" />
          <AppInput label="Description" value={values.description} onChangeText={(description) => setValues((current) => ({ ...current, description }))} error={errors.description} testID="farm-edit-description" multiline />
          {feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}
          <AppButton title="Save farm profile" onPress={submit} loading={saving} disabled={saving} testID="farm-edit-save" />
          <AppButton title="Cancel" variant="outline" onPress={() => { setEditing(false); setErrors({}); setFeedback(null); setValues({ name: details.name, location: details.location || "", description: details.description || "" }); }} disabled={saving} />
        </View> : <View style={{ gap: spacing.lg }}>
          <Detail label="Location" value={details.location || "Not provided"} />
          <Detail label="Description" value={details.description || "Not provided"} />
          <Detail label="Created" value={formatDate(details.created_at)} />
          <Detail label="Current membership" value={`${roleLabel(farm.membership?.role)} · ${farm.membership?.status || "ACTIVE"}`} />
          <Detail label="Farm identifier" value={details.id} mono />
          <Detail label="Owner identifier" value={details.owner_id} mono />
          {feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}
          {farm.can("farm.manage") ? <AppButton title="Edit farm profile" variant="outline" onPress={() => setEditing(true)} testID="farm-edit-open" /> : null}
        </View>}
      </AppCard>
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
