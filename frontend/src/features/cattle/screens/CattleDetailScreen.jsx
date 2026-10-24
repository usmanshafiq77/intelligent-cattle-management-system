import { useCallback, useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { ConfirmationDialog } from "../../../components/ui/ConfirmationDialog";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { requireCattle } from "../cattleContracts";
import { cattleErrorMessage } from "../cattleErrors";
import { optionLabel } from "../cattleOptions";
import { CattlePage } from "../components/CattlePage";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const TRANSITIONS = Object.freeze({
  ACTIVE: ["MISSING", "SOLD", "TRANSFERRED", "DECEASED", "ARCHIVED"],
  MISSING: ["ACTIVE", "DECEASED"],
});

export function CattleDetailScreen({ cattleId, onBack, onEdit, api = cattleApi }) {
  const farm = useFarm();
  return <RequireFarm><RequirePermission permission="cattle.view"><DetailContent cattleId={cattleId} farm={farm} onBack={onBack} onEdit={onEdit} api={api} /></RequirePermission></RequireFarm>;
}

function DetailContent({ cattleId, farm, onBack, onEdit, api }) {
  const { theme, spacing, typography } = useAppTheme();
  const operation = useRef(0);
  const requestController = useRef(null);
  const transition = useRef({ operation: 0, controller: null, locked: false });
  const [state, setState] = useState({ status: "loading", animal: null, error: null });
  const [transitionTarget, setTransitionTarget] = useState(null);
  const [transitionPending, setTransitionPending] = useState(false);
  const [transitionFeedback, setTransitionFeedback] = useState(null);
  const farmId = farm.activeFarm.id;

  const load = useCallback(async () => {
    requestController.current?.abort();
    if (!UUID.test(String(cattleId || ""))) {
      setState({ status: "invalid", animal: null, error: null });
      return;
    }
    const current = ++operation.current;
    const controller = new AbortController();
    requestController.current = controller;
    setState({ status: "loading", animal: null, error: null });
    try {
      const animal = requireCattle(await api.get(farmId, cattleId, { signal: controller.signal }), farmId);
      if (operation.current === current && farm.activeFarm?.id === farmId) setState({ status: "ready", animal, error: null });
    } catch (error) {
      if (operation.current === current && !error?.isCancelled) setState({ status: error?.status === 404 ? "missing" : "error", animal: null, error });
    }
  }, [api, cattleId, farm.activeFarm?.id, farmId]);

  useEffect(() => {
    void load();
    return () => { requestController.current?.abort(); transition.current.controller?.abort(); operation.current += 1; transition.current.operation += 1; transition.current.locked = false; };
  }, [load]);

  const confirmTransition = async () => {
    if (!transitionTarget || transition.current.locked || !farm.can("cattle.update")) return;
    const controller = new AbortController();
    const current = transition.current.operation + 1;
    transition.current = { operation: current, controller, locked: true };
    setTransitionPending(true);
    setTransitionFeedback(null);
    try {
      const event = await api.addLifecycleEvent(farmId, cattleId, {
        new_status: transitionTarget,
        effective_at: new Date().toISOString(),
        reason: `Status changed to ${optionLabel(transitionTarget)} from cattle profile`,
      }, { signal: controller.signal });
      if (!event || event.farm_id !== farmId || event.cattle_id !== cattleId || event.new_status !== transitionTarget) throw new Error("Invalid lifecycle response.");
      if (transition.current.operation !== current || farm.activeFarm?.id !== farmId || !farm.can("cattle.update")) return;
      transition.current.locked = false;
      setTransitionPending(false);
      setTransitionTarget(null);
      setTransitionFeedback(`Status changed to ${optionLabel(event.new_status)}.`);
      await load();
    } catch (error) {
      if (transition.current.operation !== current || error?.isCancelled || controller.signal.aborted) return;
      transition.current.locked = false;
      setTransitionPending(false);
      setTransitionTarget(null);
      setTransitionFeedback(cattleErrorMessage(error, { mutation: true }));
    }
  };

  if (state.status === "invalid") return <CattlePage title="Invalid cattle link" subtitle="The cattle identifier in this link is not valid." onBack={onBack}><FeedbackState type="error" title="Invalid cattle ID" message="Return to the cattle directory and choose a verified record." /></CattlePage>;
  if (state.status === "loading") return <CattlePage title="Cattle profile" onBack={onBack}><FeedbackState type="loading" title="Loading cattle profile" showSkeleton /></CattlePage>;
  if (state.status === "missing") return <CattlePage title="Cattle unavailable" onBack={onBack}><FeedbackState type="error" title="Cattle not found" message={cattleErrorMessage(state.error)} /></CattlePage>;
  if (state.status === "error") return <CattlePage title="Cattle unavailable" onBack={onBack}><FeedbackState type="error" title="Could not load cattle" message={cattleErrorMessage(state.error)} actionLabel="Retry" onAction={() => { void load(); }} /></CattlePage>;

  const animal = state.animal;
  const fields = [
    ["Farm", farm.activeFarm.name], ["Tag number", animal.tag_number], ["Species", optionLabel(animal.species)], ["Sex", optionLabel(animal.sex)], ["Category", optionLabel(animal.category)],
    ["Breed", animal.breed?.name || "Not specified"], ["Date of birth", animal.date_of_birth ? `${animal.date_of_birth}${animal.birth_date_estimated ? " (estimated)" : ""}` : "Not specified"],
    ["Latest weight", animal.latest_weight ? `${animal.latest_weight.weight_kg} kg` : "Not recorded"], ["Registered", animal.registration_date], ["Acquisition", optionLabel(animal.acquisition_method)],
    ["Acquisition date", animal.acquisition_date || "Not specified"], ["Acquisition source", animal.acquisition_source || "Not specified"], ["Color", animal.color || "Not specified"],
    ["Identification marks", animal.identification_marks || "Not specified"], ["Notes", animal.notes || "Not specified"], ["Media records", String(animal.media_count || 0)],
  ];

  return (
    <CattlePage title={animal.name || animal.tag_number} subtitle={`Verified cattle profile · Tag ${animal.tag_number}`} onBack={onBack} action={farm.can("cattle.update") ? <AppButton title="Edit profile" size="small" fullWidth={false} onPress={() => onEdit?.(animal.id)} /> : null}>
      <View style={{ gap: spacing.lg }}>
        {transitionFeedback ? <InlineFeedback type={transitionFeedback.startsWith("Status changed") ? "success" : "error"} message={transitionFeedback} /> : null}
        <View style={styles.statusRow}><StatusBadge status={animal.status === "ACTIVE" ? "success" : "info"} label={optionLabel(animal.status)} /><AppButton title="Refresh" variant="outline" size="small" fullWidth={false} onPress={() => { void load(); }} /></View>
        <AppCard title="Animal details" subtitle="Values below are returned by the ICMS backend.">
          <View style={styles.details}>{fields.map(([label, value]) => <View key={label} style={[styles.field, { borderBottomColor: theme.colors.border }]}><Text style={{ color: theme.colors.textSecondary, fontSize: typography.sizes.caption, fontWeight: typography.weights.bold }}>{label}</Text><Text selectable style={{ color: theme.colors.text, fontSize: typography.sizes.body, marginTop: spacing.xs }}>{value}</Text></View>)}</View>
        </AppCard>
        <AppCard title="Lifecycle operations" subtitle="Transitions follow the backend lifecycle policy. Physical delete is not supported by the API.">
          <View style={{ gap: spacing.md }}><Text style={{ color: theme.colors.textSecondary }}>Current state: {optionLabel(animal.status)}</Text>{farm.can("cattle.update") && (TRANSITIONS[animal.status] || []).length ? <View style={styles.statusActions}>{TRANSITIONS[animal.status].map((status) => <AppButton key={status} title={`Mark ${optionLabel(status)}`} variant={["DECEASED", "ARCHIVED"].includes(status) ? "danger" : "outline"} size="small" fullWidth={false} onPress={() => setTransitionTarget(status)} />)}</View> : <Text style={{ color: theme.colors.textSecondary }}>{farm.can("cattle.update") ? "No further lifecycle transitions are permitted for this status." : "Your role cannot change lifecycle status."}</Text>}</View>
        </AppCard>
      </View>
      <ConfirmationDialog visible={Boolean(transitionTarget)} title={`Change status to ${optionLabel(transitionTarget)}?`} message="This creates a permanent lifecycle event for the active farm. Confirm only when the status is accurate." confirmLabel="Confirm status" destructive={["DECEASED", "ARCHIVED"].includes(transitionTarget)} pending={transitionPending} onConfirm={confirmTransition} onCancel={() => { if (!transitionPending) setTransitionTarget(null); }} />
    </CattlePage>
  );
}

const styles = StyleSheet.create({
  statusRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12 },
  details: { flexDirection: "row", flexWrap: "wrap", gap: 16 },
  field: { minWidth: 210, flexBasis: 300, flexGrow: 1, borderBottomWidth: 1, paddingBottom: 12 },
  statusActions: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
});
