import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";
import { milkApi } from "../../../api/milk";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { StatCard } from "../../../components/ui/StatCard";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { deliverMilkCsv, milkRowsToCsv } from "../milkExport";
import { milkErrorMessage } from "../milkErrors";

const isoDay = (value = new Date()) => value.toISOString().slice(0, 10);
const shiftDay = (amount) => { const value = new Date(); value.setUTCDate(value.getUTCDate() + amount); return isoDay(value); };
const monthStart = () => `${isoDay().slice(0, 8)}01`;
const weekStart = () => { const value = new Date(); const weekday = value.getUTCDay() || 7; value.setUTCDate(value.getUTCDate() - weekday + 1); return isoDay(value); };
const liters = (value) => `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })} L`;
const cowLabel = (cow) => `${cow.tag_number}${cow.name ? ` · ${cow.name}` : ""}`;

function useResource(load, dependencies = [], enabled = true) {
  const [state, setState] = useState({ status: enabled ? "loading" : "idle", data: null, error: null });
  const operation = useRef(0);
  const refresh = useCallback(async () => {
    if (!enabled) return null;
    const current = ++operation.current;
    setState((previous) => ({ ...previous, status: "loading", error: null }));
    try {
      const data = await load();
      if (current === operation.current) setState({ status: "ready", data, error: null });
      return data;
    } catch (error) {
      if (current === operation.current) setState({ status: "error", data: null, error });
      return null;
    }
  }, [...dependencies, enabled]);
  useEffect(() => { if (enabled) void refresh(); return () => { operation.current += 1; }; }, [refresh, enabled]);
  return { ...state, refresh };
}

function Page({ title, subtitle, permission = "milk.view", onBack, children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return <Screen style={{ backgroundColor: theme.colors.background }}><RequireFarm><RequirePermission permission={permission}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.page, { maxWidth: layout.contentMaxWidth, padding: spacing.lg, gap: spacing.lg }]}>
      <View style={styles.row}><View style={styles.grow}><Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>{title}</Text><Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text></View>{onBack ? <AppButton title="Back" variant="outline" size="small" fullWidth={false} onPress={onBack} /> : null}</View>
      {children}
    </ScrollView>
  </RequirePermission></RequireFarm></Screen>;
}

function Resource({ resource, empty = "No milk records match these filters.", children }) {
  if (resource.status === "loading") return <FeedbackState type="loading" title="Loading milk records" showSkeleton />;
  if (resource.status === "error") return <FeedbackState type="error" title="Milk records unavailable" message={milkErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} />;
  if (!resource.data?.length) return <FeedbackState title="No records yet" message={empty} />;
  return children(resource.data);
}

function RecordCard({ title, subtitle, badge, children, onPress, testID }) {
  return <AppCard testID={testID} onPress={onPress} compact><View style={styles.row}><View style={styles.grow}><Text style={styles.recordTitle}>{title}</Text><Text style={styles.muted}>{subtitle}</Text></View>{badge ? <StatusBadge label={badge} status={badge === "ACTIVE" ? "success" : "neutral"} compact /> : null}</View>{children ? <View style={styles.cardBody}>{children}</View> : null}</AppCard>;
}

function CowChoices({ cows, selectedId, onSelect }) {
  if (!cows.length) return <InlineFeedback type="info" message="No active female cows are available in this farm." />;
  return <View style={styles.wrap}>{cows.map((cow) => <AppButton key={cow.id} testID={`cow-${cow.id}`} title={cowLabel(cow)} variant={selectedId === cow.id ? "primary" : "outline"} size="small" fullWidth={false} onPress={() => onSelect(cow.id)} />)}</View>;
}

function DateFilters({ value, onChange, interval, onInterval }) {
  return <AppCard title="Date range"><View style={styles.form}><View style={styles.wrap}><AppInput label="From (YYYY-MM-DD)" value={value.date_from} onChangeText={(date_from) => onChange({ ...value, date_from })} style={styles.field} /><AppInput label="To (YYYY-MM-DD)" value={value.date_to} onChangeText={(date_to) => onChange({ ...value, date_to })} style={styles.field} /></View>{interval ? <View style={styles.wrap}>{["daily", "weekly", "monthly"].map((item) => <AppButton key={item} title={item[0].toUpperCase() + item.slice(1)} variant={interval === item ? "primary" : "outline"} size="small" fullWidth={false} onPress={() => onInterval(item)} />)}</View> : null}</View></AppCard>;
}

export function detectProductionDrop(buckets, today = isoDay()) {
  const complete = (buckets || []).filter((item) => item.period_start < today).slice(-8);
  if (complete.length < 5) return null;
  const current = Number(complete.at(-1).volume_liters);
  const baselineRows = complete.slice(-5, -1);
  const baseline = baselineRows.reduce((sum, item) => sum + Number(item.volume_liters), 0) / baselineRows.length;
  if (baseline <= 0 || current >= baseline * 0.8) return null;
  return { current, baseline, reductionPercent: Math.round((1 - current / baseline) * 100), date: complete.at(-1).period_start };
}

export function MilkDashboardScreen({ onNavigate, onBack, api = milkApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const analyticsAllowed = farm.can("milk.analytics.view");
  const data = useResource(async () => {
    const sessions = await api.listSessions(id, { limit: 8 });
    if (!analyticsAllowed) return { sessions, summaries: null, breakdown: null };
    const [today, yesterday, week, month, trend, breakdown] = await Promise.all([
      api.getProductionAnalytics(id, { date_from: isoDay(), date_to: isoDay(), interval: "daily" }),
      api.getProductionAnalytics(id, { date_from: shiftDay(-1), date_to: shiftDay(-1), interval: "daily" }),
      api.getProductionAnalytics(id, { date_from: weekStart(), date_to: isoDay(), interval: "daily" }),
      api.getProductionAnalytics(id, { date_from: monthStart(), date_to: isoDay(), interval: "daily" }),
      api.getProductionAnalytics(id, { date_from: shiftDay(-14), date_to: isoDay(), interval: "daily" }),
      api.getBreakdownAnalytics(id, { date_from: isoDay(), date_to: isoDay() }),
    ]);
    return { sessions, summaries: { today, yesterday, week, month, trend }, breakdown };
  }, [api, id, analyticsAllowed]);
  const actions = [
    ["Record milk", "/milk/entry", "milk.record"], ["Milk records", "/milk/records", "milk.view"], ["Cow history", "/milk/cows", "milk.view"], ["Lactations", "/milk/lactations", "milk.view"],
    ["Corrections", "/milk/corrections", "milk.correct"], ["Analytics", "/milk/analytics", "milk.analytics.view"], ["Availability", "/milk/availability", "finance.view"], ["Reports", "/milk/reports", "milk.analytics.view"],
  ].filter(([, , permission]) => farm.can(permission));
  const anomaly = detectProductionDrop(data.data?.summaries?.trend?.buckets);
  return <Page title="Milk Production" subtitle={`Farm-scoped production for ${farm.activeFarm?.name || "the selected farm"}.`} onBack={onBack}>
    <View style={styles.wrap}>{actions.map(([label, route]) => <AppButton key={route} title={label} variant="outline" fullWidth={false} onPress={() => onNavigate(route)} />)}</View>
    {data.status === "loading" ? <FeedbackState type="loading" title="Loading milk dashboard" showSkeleton /> : null}
    {data.status === "error" ? <FeedbackState type="error" title="Milk dashboard unavailable" message={milkErrorMessage(data.error)} actionLabel="Retry" onAction={data.refresh} /> : null}
    {data.data?.summaries ? <><View style={styles.stats}><StatCard label="Today" value={liters(data.data.summaries.today.total_volume_liters)} style={styles.stat} /><StatCard label="Yesterday" value={liters(data.data.summaries.yesterday.total_volume_liters)} style={styles.stat} /><StatCard label="Current week" value={liters(data.data.summaries.week.total_volume_liters)} style={styles.stat} /><StatCard label="Current month" value={liters(data.data.summaries.month.total_volume_liters)} style={styles.stat} /><StatCard label="Cows milked today" value={String(data.data.summaries.today.recorded_animals)} style={styles.stat} /><StatCard label="Per-cow average" value={liters(data.data.summaries.today.average_per_recorded_animal_liters)} style={styles.stat} /><StatCard label="Morning" value={liters(data.data.breakdown?.session_totals?.find((row) => row.session_kind === "MORNING")?.volume_liters)} style={styles.stat} /><StatCard label="Evening" value={liters(data.data.breakdown?.session_totals?.find((row) => row.session_kind === "EVENING")?.volume_liters)} style={styles.stat} /></View>
      <AppCard title="Recent production trend"><TrendBars buckets={data.data.summaries.trend.buckets} /></AppCard>
      {anomaly ? <AppCard title="Estimated production anomaly"><View style={styles.form}><InlineFeedback type="warning" message={`${anomaly.date} was ${anomaly.reductionPercent}% below the previous four recorded days. This is not a diagnosis and missing sessions can affect the comparison.`} />{farm.can("health.view") ? <AppButton title="Review health records" variant="outline" onPress={() => onNavigate("/health")} /> : null}</View></AppCard> : <InlineFeedback type="info" message="Production-drop indicators require five completed days and never represent a veterinary diagnosis." />}</> : null}
    {data.data ? <AppCard title="Recent entries"><Resource resource={{ status: "ready", data: data.data.sessions, refresh: data.refresh }} empty="No milk has been recorded for this farm.">{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={`${liters(row.effective_volume_liters)} · ${row.session_kind}`} subtitle={`${row.milking_date} · Cow ${row.cattle_id}`} onPress={() => onNavigate(`/milk/records/${row.id}`)} />)}</View>}</Resource></AppCard> : null}
  </Page>;
}

export function DailyMilkEntryScreen({ onBack, api = milkApi, cattle = cattleApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id;
  const options = useResource(async () => { const [animals, lactations] = await Promise.all([cattle.list(id, { sex: "FEMALE", status: "ACTIVE", limit: 200 }), api.listLactations(id, { lactation_status: "ACTIVE", limit: 200 })]); return { cows: animals.filter((item) => item.category === "COW"), lactations }; }, [api, cattle, id]);
  const [form, setForm] = useState({ cattle_id: "", lactation_id: "", milking_date: isoDay(), session_kind: "MORNING", session_code: "MORNING", volume_liters: "", notes: "" });
  const [feedback, setFeedback] = useState(null); const [saving, setSaving] = useState(false);
  const chooseCow = (cattle_id) => { const active = options.data?.lactations.find((item) => item.cattle_id === cattle_id); setForm((old) => ({ ...old, cattle_id, lactation_id: active?.id || "" })); };
  const setSession = (session_kind) => setForm((old) => ({ ...old, session_kind, session_code: session_kind === "ADDITIONAL" ? "" : session_kind }));
  const submit = async () => {
    const quantity = Number(form.volume_liters);
    if (!form.cattle_id || !form.lactation_id) return setFeedback({ type: "error", message: "Select a cow with an active lactation." });
    if (!form.milking_date || form.milking_date > isoDay()) return setFeedback({ type: "error", message: "Production date is required and cannot be in the future." });
    if (!Number.isFinite(quantity) || quantity < 0) return setFeedback({ type: "error", message: "Milk quantity must be zero or a positive number." });
    if (form.session_kind === "ADDITIONAL" && !form.session_code.trim()) return setFeedback({ type: "error", message: "A distinct code is required for an additional session." });
    setSaving(true); setFeedback(null);
    try { const record = await api.createSession(id, { ...form, session_code: form.session_code.trim().toUpperCase(), volume_liters: form.volume_liters, unit: "L", notes: form.notes.trim() || null }); setFeedback({ type: "success", message: `Saved ${liters(record.effective_volume_liters)} for ${record.milking_date}.` }); setForm((old) => ({ ...old, volume_liters: "", notes: "" })); }
    catch (error) { setFeedback({ type: "error", message: milkErrorMessage(error) }); } finally { setSaving(false); }
  };
  return <Page title="Daily Milk Entry" subtitle="Record one canonical cow/date/session entry. Duplicate submissions are blocked by the server." permission="milk.record" onBack={onBack}>
    {options.status === "loading" ? <FeedbackState type="loading" title="Loading eligible cows" showSkeleton /> : null}{options.status === "error" ? <FeedbackState type="error" title="Eligible cows unavailable" message={milkErrorMessage(options.error)} actionLabel="Retry" onAction={options.refresh} /> : null}
    {options.data ? <AppCard title="Eligible cow"><CowChoices cows={options.data.cows} selectedId={form.cattle_id} onSelect={chooseCow} />{form.cattle_id && !form.lactation_id ? <InlineFeedback type="warning" message="This cow has no active lactation. An authorized manager must start one before milk can be recorded." /> : null}</AppCard> : null}
    <AppCard title="Production details"><View style={styles.form}><AppInput testID="milk-date" label="Production date" value={form.milking_date} onChangeText={(milking_date) => setForm({ ...form, milking_date })} /><View style={styles.wrap}>{["MORNING", "EVENING", "ADDITIONAL"].map((kind) => <AppButton key={kind} testID={`session-${kind.toLowerCase()}`} title={kind} variant={form.session_kind === kind ? "primary" : "outline"} size="small" fullWidth={false} onPress={() => setSession(kind)} />)}</View>{form.session_kind === "ADDITIONAL" ? <AppInput testID="milk-session-code" label="Additional session code" value={form.session_code} onChangeText={(session_code) => setForm({ ...form, session_code })} autoCapitalize="characters" /> : null}<AppInput testID="milk-volume" label="Milk quantity (litres)" value={form.volume_liters} onChangeText={(volume_liters) => setForm({ ...form, volume_liters })} keyboardType="decimal-pad" /><AppInput label="Notes (optional)" value={form.notes} onChangeText={(notes) => setForm({ ...form, notes })} multiline maxLength={5000} />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton testID="milk-submit" title="Save milk record" loading={saving} disabled={saving} onPress={submit} /></View></AppCard>
  </Page>;
}

export function MilkRecordsScreen({ onBack, onOpen, api = milkApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const [filters, setFilters] = useState({ date_from: monthStart(), date_to: isoDay(), cattle_id: "", session_kind: "", limit: 50, offset: 0 });
  const query = useMemo(() => Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "")), [filters]);
  const rows = useResource(() => api.listSessions(id, query), [api, id, JSON.stringify(query)]);
  return <Page title="Milk Records" subtitle="Effective quantities include authorized corrections while original records remain immutable." onBack={onBack}><DateFilters value={filters} onChange={setFilters} /><AppCard title="Filters"><View style={styles.wrap}><AppInput label="Cow ID (optional)" value={filters.cattle_id} onChangeText={(cattle_id) => setFilters({ ...filters, cattle_id, offset: 0 })} style={styles.field} /><AppInput label="Session (optional)" value={filters.session_kind} onChangeText={(session_kind) => setFilters({ ...filters, session_kind: session_kind.toUpperCase(), offset: 0 })} helperText="MORNING, EVENING, or ADDITIONAL" style={styles.field} /></View></AppCard><Resource resource={rows}>{(data) => <View style={styles.form}>{data.map((row) => <RecordCard key={row.id} title={`${liters(row.effective_volume_liters)} · ${row.session_kind}`} subtitle={`${row.milking_date} · Cow ${row.cattle_id}`} badge={row.session_code} onPress={onOpen ? () => onOpen(row.id) : undefined}><Text style={styles.muted}>{row.effective_notes || "No notes"}</Text></RecordCard>)}<View style={styles.wrap}><AppButton title="Previous" variant="outline" size="small" fullWidth={false} disabled={!filters.offset} onPress={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - filters.limit) })} /><AppButton title="Next" variant="outline" size="small" fullWidth={false} disabled={data.length < filters.limit} onPress={() => setFilters({ ...filters, offset: filters.offset + filters.limit })} /></View></View>}</Resource></Page>;
}

export function CowMilkHistoryScreen({ onBack, api = milkApi, cattle = cattleApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const [cowId, setCowId] = useState(""); const [range, setRange] = useState({ date_from: shiftDay(-30), date_to: isoDay() });
  const cows = useResource(async () => (await cattle.list(id, { sex: "FEMALE", limit: 200 })).filter((item) => item.category === "COW"), [cattle, id]);
  const history = useResource(() => Promise.all([api.listSessions(id, { ...range, cattle_id: cowId, limit: 200 }), api.listLactations(id, { cattle_id: cowId, limit: 100 })]), [api, id, cowId, range.date_from, range.date_to], Boolean(cowId));
  return <Page title="Cow-wise Production" subtitle="Select one cow to review production and lactation history without mixing farms." onBack={onBack}><DateFilters value={range} onChange={setRange} /><AppCard title="Cow"><Resource resource={cows} empty="No female cows are registered in this farm.">{(data) => <CowChoices cows={data} selectedId={cowId} onSelect={setCowId} />}</Resource></AppCard>{!cowId ? <FeedbackState title="Select a cow" message="Choose a cow above to load its milk and lactation history." /> : null}{history.status === "loading" ? <FeedbackState type="loading" title="Loading cow history" showSkeleton /> : null}{history.error ? <FeedbackState type="error" title="Cow history unavailable" message={milkErrorMessage(history.error)} actionLabel="Retry" onAction={history.refresh} /> : null}{history.data ? <><AppCard title="Production records">{history.data[0].length ? <View style={styles.form}>{history.data[0].map((row) => <RecordCard key={row.id} title={liters(row.effective_volume_liters)} subtitle={`${row.milking_date} · ${row.session_kind}`} />)}</View> : <Text style={styles.muted}>No production in this date range.</Text>}</AppCard><AppCard title="Lactation history">{history.data[1].length ? <View style={styles.form}>{history.data[1].map((row) => <RecordCard key={row.id} title={`Lactation ${row.sequence_number}`} subtitle={`${row.start_date} to ${row.end_date || row.dry_off_date || "ongoing"}`} badge={row.status} />)}</View> : <Text style={styles.muted}>No lactation records.</Text>}</AppCard></> : null}</Page>;
}

export function MilkRecordDetailsScreen({ sessionId, onBack, api = milkApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const canCorrect = farm.can("milk.correct");
  const record = useResource(() => api.getSession(id, sessionId), [api, id, sessionId], Boolean(sessionId));
  const audit = useResource(() => api.listCorrections(id, { target_type: "SESSION", target_id: sessionId, limit: 200 }), [api, id, sessionId], canCorrect && Boolean(sessionId));
  const [form, setForm] = useState({ volume_liters: "", notes: "", reason: "" }); const [feedback, setFeedback] = useState(null);
  const correct = async () => { const replacement_values = {}; if (form.volume_liters !== "") replacement_values.volume_liters = form.volume_liters; if (form.notes !== "") replacement_values.notes = form.notes; if (!Object.keys(replacement_values).length || form.reason.trim().length < 3) return setFeedback({ type: "error", message: "Enter a corrected value and a reason of at least three characters." }); try { await api.createCorrection(id, { cattle_id: record.data.cattle_id, target_type: "SESSION", target_id: sessionId, reason: form.reason.trim(), replacement_values }); setFeedback({ type: "success", message: "Correction recorded in the audit history." }); await Promise.all([record.refresh(), audit.refresh()]); } catch (error) { setFeedback({ type: "error", message: milkErrorMessage(error) }); } };
  return <Page title="Milk Record Details" subtitle="Original events are retained; displayed totals use the latest authorized correction." onBack={onBack}>{record.status === "loading" ? <FeedbackState type="loading" title="Loading milk record" showSkeleton /> : null}{record.error ? <FeedbackState type="error" title="Milk record unavailable" message={milkErrorMessage(record.error)} actionLabel="Retry" onAction={record.refresh} /> : null}{record.data ? <AppCard title={`${liters(record.data.effective_volume_liters)} · ${record.data.session_kind}`} subtitle={`${record.data.milking_date} · Cow ${record.data.cattle_id}`}><View style={styles.form}><Text style={styles.muted}>Session code: {record.data.session_code}</Text><Text style={styles.muted}>Recorded by: {record.data.recorded_by_id}</Text><Text style={styles.muted}>Notes: {record.data.effective_notes || "None"}</Text></View></AppCard> : null}{canCorrect && record.data ? <AppCard title="Audited correction"><View style={styles.form}><AppInput testID="correction-volume" label="Replacement litres (optional)" value={form.volume_liters} onChangeText={(volume_liters) => setForm({ ...form, volume_liters })} keyboardType="decimal-pad" /><AppInput label="Replacement notes (optional)" value={form.notes} onChangeText={(notes) => setForm({ ...form, notes })} /><AppInput testID="correction-reason" label="Reason" value={form.reason} onChangeText={(reason) => setForm({ ...form, reason })} />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton testID="correction-submit" title="Record correction" onPress={correct} /></View></AppCard> : null}{canCorrect ? <AppCard title="Correction audit history"><Resource resource={audit} empty="This record has no corrections.">{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={row.reason} subtitle={`${new Date(row.created_at).toLocaleString()} · ${row.corrected_by_id}`}><Text style={styles.muted}>Original: {JSON.stringify(row.original_values)}</Text><Text style={styles.muted}>Corrected: {JSON.stringify(row.replacement_values)}</Text></RecordCard>)}</View>}</Resource></AppCard> : null}</Page>;
}

export function MilkCorrectionsScreen({ onBack, api = milkApi }) {
  const farm = useFarm(); const rows = useResource(() => api.listCorrections(farm.activeFarm?.id, { limit: 200 }), [api, farm.activeFarm?.id]);
  return <Page title="Milk Corrections" subtitle="Append-only correction history for production and quality records." permission="milk.correct" onBack={onBack}><Resource resource={rows} empty="No milk corrections have been recorded.">{(data) => <View style={styles.form}>{data.map((row) => <RecordCard key={row.id} title={row.reason} subtitle={`${row.target_type} · ${row.target_id}`} badge={new Date(row.created_at).toLocaleDateString()}><Text style={styles.muted}>Original: {JSON.stringify(row.original_values)}</Text><Text style={styles.muted}>Effective replacement: {JSON.stringify(row.replacement_values)}</Text><Text style={styles.muted}>Corrected by {row.corrected_by_id}</Text></RecordCard>)}</View>}</Resource></Page>;
}

export function LactationRecordsScreen({ onBack, api = milkApi, cattle = cattleApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const canManage = farm.can("milk.lactation.manage");
  const resource = useResource(() => Promise.all([api.listLactations(id, { limit: 200 }), cattle.list(id, { sex: "FEMALE", status: "ACTIVE", limit: 200 })]), [api, cattle, id]);
  const [form, setForm] = useState({ cattle_id: "", sequence_number: "1", start_date: isoDay() }); const [transition, setTransition] = useState({ lactation_id: "", status: "DRY", effective_date: isoDay() }); const [feedback, setFeedback] = useState(null);
  const create = async () => { if (!form.cattle_id || Number(form.sequence_number) < 1 || form.start_date > isoDay()) return setFeedback({ type: "error", message: "Select an eligible cow, a positive sequence, and a non-future date." }); try { await api.createLactation(id, { ...form, sequence_number: Number(form.sequence_number) }); setFeedback({ type: "success", message: "Lactation started." }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: milkErrorMessage(error) }); } };
  const changeStatus = async () => { if (!transition.lactation_id) return setFeedback({ type: "error", message: "Select a lactation to transition." }); try { await api.transitionLactation(id, transition.lactation_id, { status: transition.status, effective_date: transition.effective_date }); setFeedback({ type: "success", message: `Lactation marked ${transition.status.toLowerCase()}.` }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: milkErrorMessage(error) }); } };
  return <Page title="Lactation Records" subtitle="Review lactation and dry-period status; lifecycle transitions follow existing server rules." onBack={onBack}>{canManage && resource.data ? <AppCard title="Lactation administration"><View style={styles.form}><CowChoices cows={resource.data[1].filter((item) => item.category === "COW")} selectedId={form.cattle_id} onSelect={(cattle_id) => setForm({ ...form, cattle_id })} /><AppInput testID="lactation-sequence" label="Sequence number" value={form.sequence_number} onChangeText={(sequence_number) => setForm({ ...form, sequence_number })} keyboardType="number-pad" /><AppInput testID="lactation-start" label="Start date" value={form.start_date} onChangeText={(start_date) => setForm({ ...form, start_date })} /><AppButton testID="lactation-submit" title="Start lactation" onPress={create} /><AppInput testID="transition-id" label="Lactation ID to transition" value={transition.lactation_id} onChangeText={(lactation_id) => setTransition({ ...transition, lactation_id })} /><View style={styles.wrap}>{["DRY", "COMPLETED"].map((status) => <AppButton key={status} title={status} variant={transition.status === status ? "primary" : "outline"} size="small" fullWidth={false} onPress={() => setTransition({ ...transition, status })} />)}</View><AppInput label="Effective date" value={transition.effective_date} onChangeText={(effective_date) => setTransition({ ...transition, effective_date })} /><AppButton testID="transition-submit" title="Apply lifecycle transition" onPress={changeStatus} />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}</View></AppCard> : null}<Resource resource={{ ...resource, data: resource.data?.[0] }} empty="No lactation history is recorded for this farm.">{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={`Lactation ${row.sequence_number}`} subtitle={`Cow ${row.cattle_id} · ${row.start_date} to ${row.end_date || row.dry_off_date || "ongoing"}`} badge={row.status} />)}</View>}</Resource></Page>;
}

function TrendBars({ buckets }) {
  const { theme } = useAppTheme(); const maximum = Math.max(1, ...(buckets || []).map((item) => Number(item.volume_liters)));
  if (!buckets?.length) return <FeedbackState title="No production observations" message="Missing dates are not converted to zero-volume observations." />;
  return <View accessibilityLabel="Milk production trend" style={styles.chart}>{buckets.map((item) => <View key={item.period_start} style={styles.barRow}><Text style={[styles.barLabel, { color: theme.colors.textSecondary }]}>{item.period_start}</Text><View style={[styles.barTrack, { backgroundColor: theme.colors.surfaceSecondary }]}><View style={[styles.bar, { backgroundColor: theme.colors.primary, width: `${Math.max(2, Number(item.volume_liters) / maximum * 100)}%` }]} /></View><Text style={[styles.barValue, { color: theme.colors.text }]}>{liters(item.volume_liters)}</Text></View>)}</View>;
}

export function MilkAnalyticsScreen({ onBack, api = milkApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const [range, setRange] = useState({ date_from: shiftDay(-30), date_to: isoDay() }); const [interval, setInterval] = useState("daily");
  const resource = useResource(() => Promise.all([api.getProductionAnalytics(id, { ...range, interval }), api.getBreakdownAnalytics(id, range)]), [api, id, range.date_from, range.date_to, interval]);
  return <Page title="Milk Analytics" subtitle="Recorded observations only; missing dates are not silently treated as zero yield." permission="milk.analytics.view" onBack={onBack}><DateFilters value={range} onChange={setRange} interval={interval} onInterval={setInterval} />{resource.status === "loading" ? <FeedbackState type="loading" title="Calculating production analytics" showSkeleton /> : null}{resource.error ? <FeedbackState type="error" title="Analytics unavailable" message={milkErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} /> : null}{resource.data ? <><View style={styles.stats}><StatCard label="Total production" value={liters(resource.data[0].total_volume_liters)} style={styles.stat} /><StatCard label="Recorded cows" value={String(resource.data[0].recorded_animals)} style={styles.stat} /><StatCard label="Session records" value={String(resource.data[0].record_count)} style={styles.stat} /><StatCard label="Average per recorded cow" value={liters(resource.data[0].average_per_recorded_animal_liters)} style={styles.stat} /></View><AppCard title="Production trend"><TrendBars buckets={resource.data[0].buckets} /></AppCard><AppCard title="Session comparison"><View style={styles.form}>{resource.data[1].session_totals.map((row) => <RecordCard key={row.session_kind} title={row.session_kind} subtitle={liters(row.volume_liters)} />)}</View></AppCard><AppCard title="Cow comparison"><View style={styles.form}>{resource.data[1].animal_totals.map((row) => <RecordCard key={row.cattle_id} title={`Cow ${row.cattle_id}`} subtitle={liters(row.volume_liters)} />)}</View></AppCard></> : null}</Page>;
}

export function MilkAvailabilityScreen({ onBack, api = milkApi }) {
  const farm = useFarm(); const allowed = farm.can("finance.view"); const resource = useResource(() => api.getAvailability(farm.activeFarm?.id), [api, farm.activeFarm?.id], allowed);
  return <Page title="Milk Availability" subtitle="Production and sold quantity are reconciled here; Finance remains authoritative for prices, payments, and income." onBack={onBack}>{!allowed ? <FeedbackState type="error" title="Finance permission required" message="Availability includes sales quantities and is restricted to members with verified Finance access." /> : null}{allowed && resource.status === "loading" ? <FeedbackState type="loading" title="Reconciling milk availability" showSkeleton /> : null}{resource.error ? <FeedbackState type="error" title="Availability unavailable" message={milkErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} /> : null}{resource.data ? <><View style={styles.stats}><StatCard label="Recorded production" value={liters(resource.data.recorded_production_liters)} style={styles.stat} /><StatCard label="Quantity sold" value={liters(resource.data.sold_liters)} style={styles.stat} /><StatCard label="Available" value={liters(resource.data.available_liters)} style={styles.stat} /></View><InlineFeedback type="info" message="Allocation/consumption and wastage are not modeled in the canonical ledger, so they are intentionally not estimated." /></> : null}</Page>;
}

export function MilkReportsScreen({ onBack, api = milkApi }) {
  const farm = useFarm(); const id = farm.activeFarm?.id; const [range, setRange] = useState({ date_from: monthStart(), date_to: isoDay() }); const [feedback, setFeedback] = useState(null);
  const report = useResource(() => Promise.all([api.getProductionAnalytics(id, { ...range, interval: "daily" }), api.getBreakdownAnalytics(id, range)]), [api, id, range.date_from, range.date_to]);
  const exportCsv = async () => { try { const rows = await api.getAnalyticsDataset(id, { ...range, limit: 5000, offset: 0 }); const action = await deliverMilkCsv(milkRowsToCsv(rows), `milk-production-${range.date_from}-${range.date_to}.csv`); setFeedback({ type: "success", message: `CSV report ${action}.` }); } catch (error) { setFeedback({ type: "error", message: milkErrorMessage(error) }); } };
  return <Page title="Milk Production Reports" subtitle="Farm-scoped daily, session, cow, and lactation dataset reporting from canonical records." permission="milk.analytics.view" onBack={onBack}><DateFilters value={range} onChange={setRange} />{report.status === "loading" ? <FeedbackState type="loading" title="Preparing milk report" showSkeleton /> : null}{report.error ? <FeedbackState type="error" title="Report unavailable" message={milkErrorMessage(report.error)} actionLabel="Retry" onAction={report.refresh} /> : null}{report.data ? <><View style={styles.stats}><StatCard label="Production" value={liters(report.data[0].total_volume_liters)} style={styles.stat} /><StatCard label="Cows" value={String(report.data[0].recorded_animals)} style={styles.stat} /><StatCard label="Sessions" value={String(report.data[0].record_count)} style={styles.stat} /></View><AppCard title="Daily report"><TrendBars buckets={report.data[0].buckets} /></AppCard><AppCard title="Session report"><View style={styles.form}>{report.data[1].session_totals.map((row) => <RecordCard key={row.session_kind} title={row.session_kind} subtitle={liters(row.volume_liters)} />)}</View></AppCard></> : null}{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton testID="milk-export-csv" title="Export CSV" variant="outline" onPress={exportCsv} /><Text style={styles.muted}>CSV is implemented for up to 5,000 rows per export. PDF and Excel exports are not claimed by this module.</Text></Page>;
}

const styles = StyleSheet.create({
  page: { width: "100%", alignSelf: "center", paddingBottom: 48 }, row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }, grow: { flex: 1, minWidth: 0 }, wrap: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 10 }, form: { gap: 12 }, field: { flex: 1, minWidth: 220 }, stats: { flexDirection: "row", flexWrap: "wrap", gap: 12 }, stat: { flex: 1, minWidth: 180 }, recordTitle: { fontWeight: "700", fontSize: 16 }, muted: { color: "#637083", lineHeight: 20 }, cardBody: { marginTop: 10, gap: 5 }, chart: { gap: 10 }, barRow: { flexDirection: "row", alignItems: "center", gap: 8 }, barLabel: { width: 88, fontSize: 12 }, barTrack: { flex: 1, height: 12, borderRadius: 6, overflow: "hidden" }, bar: { height: "100%", borderRadius: 6 }, barValue: { width: 76, textAlign: "right", fontSize: 12 },
});
