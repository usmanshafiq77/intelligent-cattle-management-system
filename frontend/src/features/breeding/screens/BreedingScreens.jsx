import { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { breedingApi } from "../../../api/breeding";
import { healthApi } from "../../../api/health";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { StatCard } from "../../../components/ui/StatCard";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { breedingErrorMessage } from "../breedingErrors";

const isoNow = () => new Date().toISOString();
const today = () => isoNow().slice(0, 10);
const monthStart = () => `${today().slice(0, 8)}01`;
const uid = () => {
  const p = () => Math.floor(Math.random() * 0xffffffff).toString(16).padStart(8, "0");
  const x = `${p()}${p()}${p()}${p()}`.slice(0, 32);
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-4${x.slice(13, 16)}-a${x.slice(17, 20)}-${x.slice(20)}`;
};

function useResource(loader, dependencies = []) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const refresh = useCallback(async () => {
    setState((old) => ({ ...old, status: "loading", error: null }));
    try { const data = await loader(); setState({ status: "ready", data, error: null }); return data; }
    catch (error) { setState({ status: "error", data: null, error }); return null; }
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}

function Page({ title, subtitle, permission = "breeding.view", onBack, children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return <Screen><RequireFarm><RequirePermission permission={permission}><ScrollView contentContainerStyle={[styles.page, { maxWidth: layout.contentMaxWidth, padding: spacing.lg, gap: spacing.lg }]}>
    <View style={styles.row}><View style={styles.grow}><Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>{title}</Text><Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text></View>{onBack ? <AppButton title="Back" variant="outline" size="small" fullWidth={false} onPress={onBack} /> : null}</View>
    {children}
  </ScrollView></RequirePermission></RequireFarm></Screen>;
}

function Resource({ resource, empty = "No records found", children }) {
  if (resource.status === "loading") return <FeedbackState type="loading" title="Loading breeding records" message="Retrieving farm-scoped information." showSkeleton />;
  if (resource.status === "error") return <FeedbackState type="error" title="Breeding records unavailable" message={breedingErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} />;
  if (!resource.data?.length) return <FeedbackState title={empty} message="New records will appear here after an authorized user submits them." />;
  return children(resource.data);
}

function Submit({ action, label, testID, onDone }) {
  const [state, setState] = useState({ busy: false, error: null, ok: false });
  return <View style={styles.formActions}>{state.error ? <InlineFeedback type="error" message={breedingErrorMessage(state.error)} /> : null}{state.ok ? <InlineFeedback type="success" message="Saved successfully." /> : null}<AppButton title={state.busy ? "Saving..." : label} testID={testID} disabled={state.busy} onPress={async () => { setState({ busy: true, error: null, ok: false }); try { await action(); setState({ busy: false, error: null, ok: true }); await onDone?.(); } catch (error) { setState({ busy: false, error, ok: false }); } }} /></View>;
}

function RecordCard({ title, subtitle, badge, children }) {
  const { theme, spacing, typography } = useAppTheme();
  return <AppCard><View style={[styles.row, { gap: spacing.sm }]}><View style={styles.grow}><Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>{title}</Text>{subtitle ? <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text> : null}</View>{badge ? <StatusBadge status="info" label={badge} compact /> : null}</View>{children}</AppCard>;
}

const NAV = [
  ["Heat cycles", "/breeding/heat", "breeding.view"], ["Breeding events", "/breeding/events", "breeding.view"], ["Pregnancy", "/breeding/pregnancy", "breeding.view"], ["Calving", "/breeding/calving", "breeding.view"], ["Register offspring", "/breeding/offspring", "breeding.calving.record"], ["Pedigree", "/breeding/pedigree", "breeding.view"], ["Calendar", "/breeding/calendar", "breeding.view"], ["Reports", "/breeding/reports", "breeding.reports.view"], ["Settings & reminders", "/breeding/settings", "breeding.manage"],
  ["Reproductive treatments", "/breeding/treatments", "health.view"],
];

export function BreedingDashboardScreen({ api = breedingApi, onBack, onNavigate }) {
  const farm = useFarm();
  const stats = useResource(() => api.dashboard(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  const reminders = useResource(() => api.listReminders(farm.activeFarm.id, { status: "OPEN" }), [farm.activeFarm?.id, api]);
  return <Page title={farm.membership?.role === "VETERINARIAN" ? "Reproductive Health Dashboard" : "Breeding & Genetics"} subtitle="Verified farm records only; estimates and clinical confirmations remain clearly separated." onBack={onBack}>
    {stats.status === "ready" ? <View style={styles.grid}>{Object.entries(stats.data).map(([key, value]) => <StatCard key={key} label={key.replaceAll("_", " ")} value={String(value)} />)}</View> : <Resource resource={{ ...stats, data: stats.data ? [stats.data] : [] }}>{() => null}</Resource>}
    <View style={styles.grid}>{NAV.filter(([, , permission]) => farm.can(permission)).map(([title, route]) => <AppButton key={route} title={title} variant="outline" onPress={() => onNavigate(route)} />)}</View>
    <Text accessibilityRole="header">Upcoming reminders</Text><Resource resource={reminders} empty="No open breeding reminders">{(rows) => rows.slice(0, 5).map((row) => <RecordCard key={row.id} title={row.title} subtitle={new Date(row.due_at).toLocaleString()} badge={row.is_estimate ? "Estimate" : row.status} />)}</Resource>
  </Page>;
}

export function HeatCycleScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listHeat(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  const [form, set] = useState({ cattle_id: "", observed_at: isoNow(), signs: "", intensity: "MODERATE", cycle_length_days: "21" });
  return <Page title="Heat Cycle Records" subtitle="Observed signs plus a clearly labeled cycle-based estimate." onBack={onBack}>
    {farm.can("breeding.heat.record") ? <AppCard><AppInput label="Cattle ID" testID="heat-cattle" value={form.cattle_id} onChangeText={(v) => set({ ...form, cattle_id: v })} /><AppInput label="Observed at (ISO with timezone)" value={form.observed_at} onChangeText={(v) => set({ ...form, observed_at: v })} /><AppInput label="Signs and symptoms" testID="heat-signs" value={form.signs} onChangeText={(v) => set({ ...form, signs: v })} multiline /><AppInput label="Intensity (LOW / MODERATE / HIGH)" value={form.intensity} onChangeText={(v) => set({ ...form, intensity: v.toUpperCase() })} /><AppInput label="Estimated cycle length (17-25 days)" value={form.cycle_length_days} onChangeText={(v) => set({ ...form, cycle_length_days: v })} keyboardType="numeric" /><Submit label="Record heat observation" testID="heat-submit" action={() => { if (!form.cattle_id || form.signs.trim().length < 2) throw new Error("Cattle and observed signs are required."); return api.createHeat(farm.activeFarm.id, { ...form, client_request_id: uid(), cycle_length_days: Number(form.cycle_length_days), create_reminder: true }); }} onDone={rows.refresh} /></AppCard> : null}
    <Resource resource={rows} empty="No heat observations">{(data) => data.map((x) => <RecordCard key={x.id} title={x.signs} subtitle={new Date(x.observed_at).toLocaleString()} badge={x.intensity || "Observed"}><Text>Estimated next heat: {x.estimated_next_heat_at ? new Date(x.estimated_next_heat_at).toLocaleString() : "Not calculated"}</Text><Text>{x.estimate_disclaimer}</Text></RecordCard>)}</Resource>
  </Page>;
}

export function BreedingEventsScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listEvents(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  const [form, set] = useState({ cow_id: "", sire_id: "", method: "ARTIFICIAL_INSEMINATION", status: "PLANNED", scheduled_at: isoNow(), semen_reference: "", technician_name: "" });
  return <Page title="Breeding Events" subtitle="Plan and record AI or natural mating without inferring conception." onBack={onBack}>
    {farm.can("breeding.event.record") ? <AppCard><AppInput label="Cow ID" testID="event-cow" value={form.cow_id} onChangeText={(v) => set({ ...form, cow_id: v })} /><AppInput label="Sire ID (required for natural mating)" value={form.sire_id} onChangeText={(v) => set({ ...form, sire_id: v })} /><AppInput label="Method" value={form.method} onChangeText={(v) => set({ ...form, method: v.toUpperCase() })} /><AppInput label="Status" value={form.status} onChangeText={(v) => set({ ...form, status: v.toUpperCase() })} /><AppInput label="Scheduled at" value={form.scheduled_at} onChangeText={(v) => set({ ...form, scheduled_at: v })} /><AppInput label="Semen reference" value={form.semen_reference} onChangeText={(v) => set({ ...form, semen_reference: v })} /><AppInput label="Technician" value={form.technician_name} onChangeText={(v) => set({ ...form, technician_name: v })} /><Submit label="Save breeding event" testID="event-submit" action={() => api.createEvent(farm.activeFarm.id, { ...form, client_request_id: uid(), sire_id: form.sire_id || null, semen_reference: form.semen_reference || null, technician_name: form.technician_name || null, completed_at: form.status === "COMPLETED" ? form.scheduled_at : null })} onDone={rows.refresh} /></AppCard> : null}
    <Resource resource={rows} empty="No breeding events">{(data) => data.map((x) => <RecordCard key={x.id} title={x.method.replaceAll("_", " ")} subtitle={new Date(x.scheduled_at).toLocaleString()} badge={x.status}><Text>{x.conception_disclaimer}</Text></RecordCard>)}</Resource>
  </Page>;
}

export function PregnancyTrackingScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listExams(farm.activeFarm.id), [farm.activeFarm?.id, api]); const losses = useResource(() => api.listLosses(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  const [form, set] = useState({ cattle_id: "", breeding_event_id: "", examined_at: isoNow(), assessment: "INCONCLUSIVE", clinical_assessment: "", gestation_days_used: "283", follow_up_at: "" });
  const [loss, setLoss] = useState({ cattle_id: "", pregnancy_examination_id: "", occurred_on: today(), loss_type: "SUSPECTED", clinical_assessment: "", follow_up_at: "" });
  const clinical = farm.membership?.role === "VETERINARIAN" && farm.can("breeding.pregnancy.assess");
  return <Page title="Pregnancy Tracking" subtitle="Veterinarian-signed clinical history; earlier assessments are retained." onBack={onBack}>
    {clinical ? <AppCard><AppInput label="Cattle ID" testID="exam-cattle" value={form.cattle_id} onChangeText={(v) => set({ ...form, cattle_id: v })} /><AppInput label="Breeding event ID (optional)" value={form.breeding_event_id} onChangeText={(v) => set({ ...form, breeding_event_id: v })} /><AppInput label="Assessment (PREGNANT / NOT_PREGNANT / INCONCLUSIVE)" value={form.assessment} onChangeText={(v) => set({ ...form, assessment: v.toUpperCase() })} /><AppInput label="Clinical assessment" testID="exam-assessment" value={form.clinical_assessment} onChangeText={(v) => set({ ...form, clinical_assessment: v })} multiline /><AppInput label="Examined at" value={form.examined_at} onChangeText={(v) => set({ ...form, examined_at: v })} /><AppInput label="Gestation days for estimate" value={form.gestation_days_used} onChangeText={(v) => set({ ...form, gestation_days_used: v })} /><Submit label="Sign pregnancy examination" testID="exam-submit" action={() => api.createExam(farm.activeFarm.id, { ...form, client_request_id: uid(), breeding_event_id: form.breeding_event_id || null, gestation_days_used: form.assessment === "PREGNANT" ? Number(form.gestation_days_used) : null, calculate_expected_calving: form.assessment === "PREGNANT", follow_up_at: form.follow_up_at || null })} onDone={rows.refresh} /></AppCard> : <InlineFeedback type="info" message="Clinical pregnancy diagnosis is available only to an authorized Veterinarian. You may view signed results." />}
    <Resource resource={rows} empty="No pregnancy examinations">{(data) => data.map((x) => <RecordCard key={x.id} title={x.assessment.replaceAll("_", " ")} subtitle={x.clinical_assessment} badge="Veterinarian signed"><Text>Expected calving: {x.expected_calving_date || "Not estimated"}</Text><Text>{x.estimate_disclaimer}</Text></RecordCard>)}</Resource>
    <Text accessibilityRole="header">Pregnancy loss history</Text>{clinical ? <AppCard><AppInput label="Cattle ID" testID="loss-cattle" value={loss.cattle_id} onChangeText={(v) => setLoss({ ...loss, cattle_id: v })} /><AppInput label="Pregnancy examination ID (optional)" value={loss.pregnancy_examination_id} onChangeText={(v) => setLoss({ ...loss, pregnancy_examination_id: v })} /><AppInput label="Occurred on" value={loss.occurred_on} onChangeText={(v) => setLoss({ ...loss, occurred_on: v })} /><AppInput label="Assessment type (SUSPECTED / CONFIRMED)" value={loss.loss_type} onChangeText={(v) => setLoss({ ...loss, loss_type: v.toUpperCase() })} /><AppInput label="Clinical assessment" value={loss.clinical_assessment} onChangeText={(v) => setLoss({ ...loss, clinical_assessment: v })} multiline /><Submit label="Record pregnancy loss assessment" testID="loss-submit" action={() => api.createLoss(farm.activeFarm.id, { ...loss, client_request_id: uid(), pregnancy_examination_id: loss.pregnancy_examination_id || null, follow_up_at: loss.follow_up_at || null })} onDone={losses.refresh} /></AppCard> : null}<Resource resource={losses} empty="No pregnancy losses recorded">{(data) => data.map((x) => <RecordCard key={x.id} title={x.loss_type} subtitle={x.clinical_assessment} badge={x.occurred_on} />)}</Resource>
  </Page>;
}

export function CalvingManagementScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listCalvings(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  const [form, set] = useState({ dam_id: "", calved_at: isoNow(), outcome: "LIVE_BIRTH", delivery_type: "NORMAL", calf_count: "1", live_count: "1", stillborn_count: "0", factual_observations: "", assistance_details: "" });
  const [clinical, setClinical] = useState({ calving_id: "", clinical_complications: "", clinical_diagnosis: "", post_calving_follow_up_at: "" });
  return <Page title="Calving Management" subtitle="Owners and Workers record facts; Veterinarians separately sign clinical complications." onBack={onBack}>
    {farm.can("breeding.calving.record") ? <AppCard><AppInput label="Dam ID" testID="calving-dam" value={form.dam_id} onChangeText={(v) => set({ ...form, dam_id: v })} /><AppInput label="Calved at" value={form.calved_at} onChangeText={(v) => set({ ...form, calved_at: v })} /><AppInput label="Outcome" value={form.outcome} onChangeText={(v) => set({ ...form, outcome: v.toUpperCase() })} /><AppInput label="Delivery type" value={form.delivery_type} onChangeText={(v) => set({ ...form, delivery_type: v.toUpperCase() })} /><AppInput label="Total calves" value={form.calf_count} onChangeText={(v) => set({ ...form, calf_count: v })} /><AppInput label="Live" value={form.live_count} onChangeText={(v) => set({ ...form, live_count: v })} /><AppInput label="Stillborn" value={form.stillborn_count} onChangeText={(v) => set({ ...form, stillborn_count: v })} /><AppInput label="Factual observations" value={form.factual_observations} onChangeText={(v) => set({ ...form, factual_observations: v })} multiline /><Submit label="Record calving facts" testID="calving-submit" action={() => api.createCalving(farm.activeFarm.id, { ...form, client_request_id: uid(), calf_count: Number(form.calf_count), live_count: Number(form.live_count), stillborn_count: Number(form.stillborn_count), factual_observations: form.factual_observations || null, assistance_details: form.assistance_details || null })} onDone={rows.refresh} /></AppCard> : null}
    {farm.membership?.role === "VETERINARIAN" && farm.can("breeding.pregnancy.assess") ? <AppCard><AppInput label="Calving event ID" testID="clinical-calving" value={clinical.calving_id} onChangeText={(v) => setClinical({ ...clinical, calving_id: v })} /><AppInput label="Clinical complications" testID="clinical-complications" value={clinical.clinical_complications} onChangeText={(v) => setClinical({ ...clinical, clinical_complications: v })} multiline /><AppInput label="Clinical diagnosis (optional)" value={clinical.clinical_diagnosis} onChangeText={(v) => setClinical({ ...clinical, clinical_diagnosis: v })} multiline /><AppInput label="Follow-up at (optional)" value={clinical.post_calving_follow_up_at} onChangeText={(v) => setClinical({ ...clinical, post_calving_follow_up_at: v })} /><Submit label="Sign clinical calving assessment" testID="clinical-calving-submit" action={() => { if (!clinical.calving_id) throw new Error("Calving event ID is required."); const { calving_id, ...payload } = clinical; return api.updateCalvingClinical(farm.activeFarm.id, calving_id, { ...payload, clinical_diagnosis: payload.clinical_diagnosis || null, post_calving_follow_up_at: payload.post_calving_follow_up_at || null }); }} onDone={rows.refresh} /></AppCard> : null}<Resource resource={rows} empty="No calving events">{(data) => data.map((x) => <RecordCard key={x.id} title={`${x.live_count} live / ${x.stillborn_count} stillborn`} subtitle={new Date(x.calved_at).toLocaleString()} badge={x.delivery_type}><Text>{x.factual_observations || "No factual notes"}</Text>{x.clinical_diagnosis ? <Text>Clinical: {x.clinical_diagnosis}</Text> : null}</RecordCard>)}</Resource>
  </Page>;
}

export function OffspringRegistrationScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const [form, set] = useState({ calving_id: "", tag_number: "", name: "", sex: "FEMALE", species: "CATTLE", category: "CALF", breed_id: "", birth_weight_kg: "", sire_id: "", birth_order: "1" });
  return <Page title="Offspring Registration" subtitle="Creates one canonical cattle record and links recorded dam and known sire atomically." permission="breeding.calving.record" onBack={onBack}><AppCard><AppInput label="Calving event ID" testID="offspring-calving" value={form.calving_id} onChangeText={(v) => set({ ...form, calving_id: v })} /><AppInput label="Calf tag" testID="offspring-tag" value={form.tag_number} onChangeText={(v) => set({ ...form, tag_number: v })} /><AppInput label="Name" value={form.name} onChangeText={(v) => set({ ...form, name: v })} /><AppInput label="Sex" value={form.sex} onChangeText={(v) => set({ ...form, sex: v.toUpperCase() })} /><AppInput label="Species" value={form.species} onChangeText={(v) => set({ ...form, species: v.toUpperCase() })} /><AppInput label="Breed ID (optional)" value={form.breed_id} onChangeText={(v) => set({ ...form, breed_id: v })} /><AppInput label="Birth weight kg (optional)" value={form.birth_weight_kg} onChangeText={(v) => set({ ...form, birth_weight_kg: v })} /><AppInput label="Known sire ID (optional)" value={form.sire_id} onChangeText={(v) => set({ ...form, sire_id: v })} /><AppInput label="Birth order" value={form.birth_order} onChangeText={(v) => set({ ...form, birth_order: v })} /><Submit label="Register newborn calf" testID="offspring-submit" action={() => { if (!form.calving_id || !form.tag_number) throw new Error("Calving event and calf tag are required."); const { calving_id, ...payload } = form; return api.registerOffspring(farm.activeFarm.id, calving_id, { ...payload, client_request_id: uid(), name: form.name || null, breed_id: form.breed_id || null, birth_weight_kg: form.birth_weight_kg || null, sire_id: form.sire_id || null, birth_order: Number(form.birth_order) }); }} /></AppCard></Page>;
}

export function PedigreeScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const [cattleId, setCattle] = useState(""); const [resource, setResource] = useState({ status: "idle", data: null, error: null }); const [parent, setParent] = useState({ child_id: "", parent_id: "", parent_role: "DAM", status: "REPORTED", confidence_percent: "", evidence_reference: "" });
  const load = async () => { setResource({ status: "loading", data: null, error: null }); try { const data = await api.pedigree(farm.activeFarm.id, cattleId, { generations: 4 }); setResource({ status: "ready", data, error: null }); } catch (error) { setResource({ status: "error", data: null, error }); } };
  return <Page title="Pedigree / Family Tree" subtitle="Recorded lineage only; incomplete parentage is never invented." onBack={onBack}><AppCard><AppInput label="Cattle ID" testID="pedigree-cattle" value={cattleId} onChangeText={setCattle} /><AppButton title="Load family tree" testID="pedigree-load" disabled={!cattleId} onPress={load} /></AppCard>{resource.status === "loading" ? <FeedbackState type="loading" title="Loading pedigree" showSkeleton /> : null}{resource.error ? <InlineFeedback type="error" message={breedingErrorMessage(resource.error)} /> : null}{resource.data ? <AppCard><RecordCard title={resource.data.subject.tag_number} subtitle="Subject" />{resource.data.ancestors.map((x) => <RecordCard key={`${x.cattle_id}-${x.generation}`} title={`${"—".repeat(x.generation)} ${x.tag_number}`} subtitle={`Generation ${x.generation} · ${x.relationship}`} badge={x.parentage_status || "Unverified"} />)}<InlineFeedback type="info" message={resource.data.limitation} /></AppCard> : null}{farm.can("breeding.pedigree.manage") ? <AppCard><AppInput label="Child ID" value={parent.child_id} onChangeText={(v) => setParent({ ...parent, child_id: v })} /><AppInput label="Parent ID" value={parent.parent_id} onChangeText={(v) => setParent({ ...parent, parent_id: v })} /><AppInput label="Role (DAM / SIRE)" value={parent.parent_role} onChangeText={(v) => setParent({ ...parent, parent_role: v.toUpperCase() })} /><AppInput label="Verification status" value={parent.status} onChangeText={(v) => setParent({ ...parent, status: v.toUpperCase() })} /><AppInput label="Confidence % (optional)" value={parent.confidence_percent} onChangeText={(v) => setParent({ ...parent, confidence_percent: v })} /><Submit label="Record validated parentage" testID="parentage-submit" action={() => api.setParentage(farm.activeFarm.id, { ...parent, client_request_id: uid(), confidence_percent: parent.confidence_percent || null, evidence_reference: parent.evidence_reference || null })} /></AppCard> : null}</Page>;
}

export function BreedingCalendarScreen({ api = breedingApi, onBack, title = "Breeding Calendar" }) {
  const farm = useFarm(); const rows = useResource(() => api.listReminders(farm.activeFarm.id, { status: "OPEN" }), [farm.activeFarm?.id, api]);
  return <Page title={title} subtitle="Expected heats, examinations, calvings, and follow-ups in local display time." onBack={onBack}><Resource resource={rows} empty="No upcoming reminders">{(data) => data.map((x) => <RecordCard key={x.id} title={x.title} subtitle={new Date(x.due_at).toLocaleString()} badge={x.is_estimate ? "Estimate" : x.reminder_type}><Text>{x.notes || "No notes"}</Text>{x.status === "OPEN" ? <AppButton title="Mark completed" size="small" variant="outline" onPress={async () => { await api.updateReminder(farm.activeFarm.id, x.id, { status: "COMPLETED" }); await rows.refresh(); }} /> : null}</RecordCard>)}</Resource></Page>;
}

export function BreedingSettingsScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listReminders(farm.activeFarm.id, { status: "OPEN" }), [farm.activeFarm?.id, api]);
  const [form, set] = useState({ cattle_id: "", reminder_type: "BREEDING_FOLLOW_UP", due_at: isoNow(), title: "", notes: "", assigned_to_id: "", is_estimate: false });
  return <Page title="Breeding Settings & Reminders" subtitle="Configure farm-scoped follow-ups; estimated dates remain labeled." permission="breeding.manage" onBack={onBack}><AppCard><AppInput label="Cattle ID" testID="reminder-cattle" value={form.cattle_id} onChangeText={(v) => set({ ...form, cattle_id: v })} /><AppInput label="Reminder type" value={form.reminder_type} onChangeText={(v) => set({ ...form, reminder_type: v.toUpperCase() })} /><AppInput label="Due at" value={form.due_at} onChangeText={(v) => set({ ...form, due_at: v })} /><AppInput label="Title" testID="reminder-title" value={form.title} onChangeText={(v) => set({ ...form, title: v })} /><AppInput label="Notes" value={form.notes} onChangeText={(v) => set({ ...form, notes: v })} /><AppInput label="Assign to user ID (optional)" value={form.assigned_to_id} onChangeText={(v) => set({ ...form, assigned_to_id: v })} /><Submit label="Create breeding reminder" testID="reminder-submit" action={() => api.createReminder(farm.activeFarm.id, { ...form, client_request_id: uid(), notes: form.notes || null, assigned_to_id: form.assigned_to_id || null })} onDone={rows.refresh} /></AppCard><Resource resource={rows} empty="No configured reminders">{(data) => data.map((x) => <RecordCard key={x.id} title={x.title} subtitle={new Date(x.due_at).toLocaleString()} badge={x.is_estimate ? "Estimate" : x.reminder_type} />)}</Resource></Page>;
}

export function BreedingReportsScreen({ api = breedingApi, onBack }) {
  const farm = useFarm(); const [range, set] = useState({ date_from: monthStart(), date_to: today() }); const report = useResource(() => api.report(farm.activeFarm.id, range), [farm.activeFarm?.id, api, range.date_from, range.date_to]);
  return <Page title="Breeding Reports" subtitle="Date-filtered factual indicators; insufficient data is reported rather than fabricated." permission="breeding.reports.view" onBack={onBack}><View style={styles.row}><AppInput label="From" value={range.date_from} onChangeText={(v) => set({ ...range, date_from: v })} /><AppInput label="To" value={range.date_to} onChangeText={(v) => set({ ...range, date_to: v })} /></View>{report.status === "ready" ? <AppCard><View style={styles.grid}>{Object.entries(report.data).filter(([, v]) => typeof v === "number" || v === null).map(([k, v]) => <StatCard key={k} label={k.replaceAll("_", " ")} value={v === null ? "Insufficient data" : String(v)} />)}</View><InlineFeedback type="info" message={report.data.data_note} /></AppCard> : <Resource resource={{ ...report, data: report.data ? [report.data] : [] }}>{() => null}</Resource>}</Page>;
}

export function ReproductiveTreatmentScreen({ api = healthApi, onBack }) {
  const farm = useFarm(); const rows = useResource(() => api.listTreatments(farm.activeFarm.id), [farm.activeFarm?.id, api]);
  return <Page title="Reproductive Treatment Records" subtitle="Clinical treatment data remains in the established Health module and is shown here without duplication." permission="health.view" onBack={onBack}><Resource resource={rows} empty="No treatment plans">{(data) => data.map((x) => <RecordCard key={x.id} title={x.name || x.treatment_name || "Treatment plan"} subtitle={x.instructions || x.notes} badge={x.status} />)}</Resource></Page>;
}

const styles = StyleSheet.create({ page: { width: "100%", alignSelf: "center", paddingBottom: 48 }, row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }, grow: { flex: 1, minWidth: 220 }, grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 }, formActions: { marginTop: 12, gap: 8 } });
