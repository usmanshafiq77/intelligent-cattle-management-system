import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { feedApi } from "../../../api/feed";
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
import { feedErrorMessage } from "../feedErrors";

const UNITS = new Set(["KG", "G", "L", "ML", "BALE"]);
const CATEGORIES = new Set(["FORAGE", "CONCENTRATE", "SUPPLEMENT", "MINERAL", "OTHER"]);
const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${today().slice(0, 8)}01`;
const requestId = () => {
  const part = () => Math.floor(Math.random() * 0xffffffff).toString(16).padStart(8, "0");
  const value = `${part()}${part()}${part()}${part()}`.slice(0, 32);
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-4${value.slice(13, 16)}-a${value.slice(17, 20)}-${value.slice(20)}`;
};

function useResource(load, dependencies = []) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const operation = useRef(0);
  const refresh = useCallback(async () => {
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
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void refresh(); return () => { operation.current += 1; }; }, [refresh]);
  return { ...state, refresh };
}

function FeedPage({ title, subtitle, permission = "feed.view", onBack, children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <RequireFarm>
        <RequirePermission permission={permission}>
          <ScrollView contentContainerStyle={[styles.page, { maxWidth: layout.contentMaxWidth, padding: spacing.lg, gap: spacing.lg }]}>
            <View style={styles.headingRow}>
              <View style={styles.grow}>
                <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>{title}</Text>
                <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text>
              </View>
              {onBack ? <AppButton title="Back" variant="outline" size="small" fullWidth={false} onPress={onBack} /> : null}
            </View>
            {children}
          </ScrollView>
        </RequirePermission>
      </RequireFarm>
    </Screen>
  );
}

function LoadState({ resource, emptyTitle, onRetry, children }) {
  if (resource.status === "loading") return <FeedbackState type="loading" title="Loading feed information" message="Retrieving farm-scoped records." showSkeleton />;
  if (resource.status === "error") return <FeedbackState type="error" title="Feed information unavailable" message={feedErrorMessage(resource.error)} actionLabel="Retry" onAction={onRetry} />;
  if (!resource.data?.length) return <FeedbackState title={emptyTitle} message="No matching records exist for this farm yet." />;
  return children(resource.data);
}

function RecordCard({ title, subtitle, status: badge, children }) {
  const { theme, spacing, typography } = useAppTheme();
  return (
    <AppCard>
      <View style={styles.headingRow}>
        <View style={styles.grow}>
          <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>{title}</Text>
          {subtitle ? <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text> : null}
        </View>
        {badge ? <StatusBadge label={badge} status={badge === "Low stock" ? "warning" : "info"} compact /> : null}
      </View>
      {children}
    </AppCard>
  );
}

export function FeedDashboardScreen({ onNavigate, onBack, api = feedApi }) {
  const farm = useFarm();
  const farmId = farm.activeFarm?.id;
  const resource = useResource(
    () => Promise.all([api.listItems(farmId), api.lowStock(farmId), api.listSchedules(farmId)]),
    [api, farmId],
  );
  const { spacing } = useAppTheme();
  const actions = [
    ["Inventory", "/feed/inventory", "feed.view"], ["Record Feeding", "/feed/records", "feed.record"],
    ["Schedules", "/feed/schedules", "feed.view"], ["Purchases", "/feed/purchases", "feed.inventory.manage"],
    ["Low Stock", "/feed/alerts", "feed.view"], ["Nutrition Plans", "/feed/nutrition", "feed.nutrition.view"],
    ["Reports", "/feed/reports", "feed.reports.view"],
  ];
  return (
    <FeedPage title="Feed Dashboard" subtitle={`Farm-scoped feed operations for ${farm.activeFarm?.name || "the selected farm"}.`} onBack={onBack}>
      {resource.status === "loading" ? <FeedbackState type="loading" title="Loading feed dashboard" showSkeleton /> : null}
      {resource.status === "error" ? <FeedbackState type="error" title="Feed dashboard unavailable" message={feedErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} /> : null}
      {resource.status === "ready" ? (
        <View style={[styles.wrap, { gap: spacing.md }]}>
          <StatCard label="Feed Items" value={resource.data[0].length} icon="F" style={styles.stat} />
          <StatCard label="Low Stock" value={resource.data[1].length} icon="!" status={resource.data[1].length ? "warning" : "success"} style={styles.stat} />
          <StatCard label="Active Schedules" value={resource.data[2].length} icon="S" style={styles.stat} />
        </View>
      ) : null}
      <View style={[styles.wrap, { gap: spacing.md }]}>
        {actions.filter(([, , permission]) => farm.can(permission)).map(([label, href]) => (
          <AppButton key={href} title={label} variant="outline" fullWidth={false} onPress={() => onNavigate(href)} />
        ))}
      </View>
    </FeedPage>
  );
}

export function FeedInventoryScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id; const canManage = farm.can("feed.inventory.manage");
  const resource = useResource(() => Promise.all([api.listItems(farmId, { include_inactive: true }), api.stockHistory(farmId, { limit: 20 })]), [api, farmId]);
  const [form, setForm] = useState({ name: "", category: "FORAGE", unit: "KG", reorder_level: "0", description: "" });
  const [adjustment, setAdjustment] = useState({ feed_item_id: "", direction: "IN", quantity: "", reason: "" });
  const [editing, setEditing] = useState(null); const [feedback, setFeedback] = useState(null); const [saving, setSaving] = useState(false);
  const set = (key) => (value) => setForm((old) => ({ ...old, [key]: value }));
  const submit = async () => {
    if (form.name.trim().length < 2 || !CATEGORIES.has(form.category.toUpperCase()) || !UNITS.has(form.unit.toUpperCase()) || Number(form.reorder_level) < 0) {
      setFeedback({ type: "error", message: "Enter a name, supported category/unit, and non-negative reorder level." }); return;
    }
    setSaving(true); setFeedback(null);
    try {
      const payload = { name: form.name.trim(), category: form.category.toUpperCase(), reorder_level: form.reorder_level, description: form.description.trim() || null };
      if (editing) await api.updateItem(farmId, editing, payload); else await api.createItem(farmId, { ...payload, unit: form.unit.toUpperCase() });
      setForm({ name: "", category: "FORAGE", unit: "KG", reorder_level: "0", description: "" }); setEditing(null);
      setFeedback({ type: "success", message: editing ? "Feed item updated." : "Feed item created." }); await resource.refresh();
    } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } finally { setSaving(false); }
  };
  const adjustStock = async () => {
    const selected = resource.data?.[0]?.find((item) => item.id === adjustment.feed_item_id);
    const direction = adjustment.direction.toUpperCase();
    if (!selected || !["IN", "OUT"].includes(direction) || Number(adjustment.quantity) <= 0 || adjustment.reason.trim().length < 3) {
      setFeedback({ type: "error", message: "Select an item and enter IN or OUT, a positive quantity, and a clear reason." }); return;
    }
    setSaving(true); setFeedback(null);
    try {
      await api.adjustStock(farmId, { client_request_id: requestId(), feed_item_id: selected.id, direction, quantity: adjustment.quantity, unit: selected.unit, reason: adjustment.reason.trim(), reference: null, occurred_at: new Date().toISOString() });
      setAdjustment({ feed_item_id: adjustment.feed_item_id, direction: "IN", quantity: "", reason: "" });
      setFeedback({ type: "success", message: "Stock adjustment recorded with an audit trail." }); await resource.refresh();
    } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } finally { setSaving(false); }
  };
  return (
    <FeedPage title="Feed Inventory" subtitle="Balances are changed only through audited purchases, adjustments, or feeding records." onBack={onBack}>
      {canManage ? <AppCard title={editing ? "Edit Feed" : "Add Feed"}>
        <View style={styles.form}>
          <AppInput testID="feed-name" label="Feed name" required value={form.name} onChangeText={set("name")} />
          <AppInput testID="feed-category" label="Category" helperText="FORAGE, CONCENTRATE, SUPPLEMENT, MINERAL or OTHER" value={form.category} onChangeText={set("category")} autoCapitalize="characters" />
          <AppInput testID="feed-unit" label="Inventory unit" helperText="KG, G, L, ML or BALE; unit cannot change after creation" value={form.unit} onChangeText={set("unit")} disabled={Boolean(editing)} autoCapitalize="characters" />
          <AppInput testID="feed-reorder" label="Low-stock threshold" value={form.reorder_level} onChangeText={set("reorder_level")} keyboardType="decimal-pad" />
          <AppInput label="Description" value={form.description} onChangeText={set("description")} multiline />
          {feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}
          <AppButton testID="feed-item-submit" title={editing ? "Save Feed" : "Add Feed"} loading={saving} onPress={submit} />
        </View>
      </AppCard> : null}
      {canManage ? <AppCard title="Stock Adjustment" subtitle="Use only for verified receipts, losses, corrections, or physical stock counts.">
        <View style={styles.form}>
          <AppInput testID="adjustment-item" label="Feed item ID" value={adjustment.feed_item_id} onChangeText={(value) => setAdjustment((old) => ({ ...old, feed_item_id: value }))} helperText={resource.data?.[0]?.map((item) => `${item.name}: ${item.id}`).join(" | ")} />
          <AppInput testID="adjustment-direction" label="Direction" value={adjustment.direction} onChangeText={(value) => setAdjustment((old) => ({ ...old, direction: value }))} helperText="IN adds stock; OUT removes stock" autoCapitalize="characters" />
          <AppInput testID="adjustment-quantity" label="Quantity" value={adjustment.quantity} onChangeText={(value) => setAdjustment((old) => ({ ...old, quantity: value }))} keyboardType="decimal-pad" />
          <AppInput testID="adjustment-reason" label="Reason" value={adjustment.reason} onChangeText={(value) => setAdjustment((old) => ({ ...old, reason: value }))} />
          <AppButton testID="adjustment-submit" title="Record Adjustment" variant="outline" loading={saving} onPress={adjustStock} />
        </View>
      </AppCard> : null}
      <LoadState resource={{ ...resource, data: resource.data?.[0] }} emptyTitle="No feed inventory" onRetry={resource.refresh}>
        {(items) => <View style={styles.form}>{items.map((item) => <RecordCard key={item.id} title={item.name} subtitle={`${item.current_quantity} ${item.unit} · reorder at ${item.reorder_level}`} status={item.low_stock ? "Low stock" : item.is_active ? "Active" : "Inactive"}>
          {canManage ? <AppButton title="Edit" variant="outline" size="small" onPress={() => { setEditing(item.id); setForm({ name: item.name, category: item.category, unit: item.unit, reorder_level: String(item.reorder_level), description: item.description || "" }); }} /> : null}
        </RecordCard>)}</View>}
      </LoadState>
      {resource.data?.[1]?.length ? <AppCard title="Recent Stock History"><View style={styles.form}>{resource.data[1].map((row) => <Text key={row.id}>{row.movement_type}: {row.quantity} {row.unit} → {row.resulting_quantity}</Text>)}</View></AppCard> : null}
    </FeedPage>
  );
}

export function FeedPurchasesScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id;
  const resource = useResource(() => Promise.all([api.listItems(farmId), api.listPurchases(farmId, { limit: 50 })]), [api, farmId]);
  const [form, setForm] = useState({ feed_item_id: "", quantity: "", unit_cost: "", currency: "PKR", supplier: "", reference: "" });
  const [feedback, setFeedback] = useState(null); const [saving, setSaving] = useState(false); const set = (key) => (value) => setForm((old) => ({ ...old, [key]: value }));
  const selected = resource.data?.[0]?.find((item) => item.id === form.feed_item_id);
  const submit = async () => {
    if (!selected || Number(form.quantity) <= 0 || Number(form.unit_cost) < 0 || !/^[A-Za-z]{3}$/.test(form.currency)) { setFeedback({ type: "error", message: "Select an item and enter valid quantity, cost, and currency." }); return; }
    setSaving(true); try { await api.createPurchase(farmId, { client_request_id: requestId(), feed_item_id: selected.id, quantity: form.quantity, unit: selected.unit, unit_cost: form.unit_cost, currency: form.currency.toUpperCase(), supplier: form.supplier || null, reference: form.reference || null, occurred_at: new Date().toISOString() }); setFeedback({ type: "success", message: "Purchase recorded and stock updated." }); setForm({ ...form, quantity: "", unit_cost: "", supplier: "", reference: "" }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } finally { setSaving(false); }
  };
  return <FeedPage title="Feed Purchases" subtitle="Purchase cost details are restricted to authorized inventory and financial users." permission="feed.inventory.manage" onBack={onBack}>
    <AppCard title="Record Purchase"><View style={styles.form}><AppInput testID="purchase-item" label="Feed item ID" value={form.feed_item_id} onChangeText={set("feed_item_id")} helperText={resource.data?.[0]?.map((item) => `${item.name}: ${item.id}`).join(" · ")} /><AppInput testID="purchase-quantity" label="Quantity" value={form.quantity} onChangeText={set("quantity")} keyboardType="decimal-pad" /><AppInput testID="purchase-cost" label="Cost per unit" value={form.unit_cost} onChangeText={set("unit_cost")} keyboardType="decimal-pad" /><AppInput label="Currency" value={form.currency} onChangeText={set("currency")} autoCapitalize="characters" /><AppInput label="Supplier" value={form.supplier} onChangeText={set("supplier")} /><AppInput label="Invoice/reference" value={form.reference} onChangeText={set("reference")} />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton testID="purchase-submit" title="Record Purchase" loading={saving} onPress={submit} /></View></AppCard>
    <LoadState resource={{ ...resource, data: resource.data?.[1] }} emptyTitle="No feed purchases" onRetry={resource.refresh}>{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={`${row.quantity} ${row.unit}`} subtitle={`${row.total_cost} ${row.currency} · ${row.supplier || "No supplier"}`} />)}</View>}</LoadState>
  </FeedPage>;
}

export function FeedingScheduleScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id; const canManage = farm.can("feed.schedule.manage");
  const resource = useResource(() => Promise.all([api.listItems(farmId), api.listSchedules(farmId)]), [api, farmId]);
  const [form, setForm] = useState({ name: "", feed_item_id: "", group_name: "", head_count: "", quantity_per_head: "", feeding_time: "07:00:00", start_date: today() }); const [feedback, setFeedback] = useState(null); const set = (key) => (value) => setForm((old) => ({ ...old, [key]: value }));
  const selected = resource.data?.[0]?.find((item) => item.id === form.feed_item_id);
  const submit = async () => { if (!selected || form.name.trim().length < 2 || !form.group_name.trim() || Number(form.head_count) <= 0 || Number(form.quantity_per_head) <= 0) { setFeedback({ type: "error", message: "Complete the schedule, group, head count, feed item, and positive quantity." }); return; } try { await api.createSchedule(farmId, { name: form.name, feed_item_id: selected.id, target_type: "GROUP", group_name: form.group_name, head_count: Number(form.head_count), quantity_per_head: form.quantity_per_head, unit: selected.unit, frequency: "DAILY", days_of_week: [], feeding_time: form.feeding_time, start_date: form.start_date }); setFeedback({ type: "success", message: "Feeding schedule created." }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } };
  return <FeedPage title="Feeding Schedule" subtitle="Workers can view farm schedules; only authorized users can create or change them." onBack={onBack}>{canManage ? <AppCard title="Add Group Schedule"><View style={styles.form}><AppInput label="Schedule name" value={form.name} onChangeText={set("name")} /><AppInput label="Feed item ID" value={form.feed_item_id} onChangeText={set("feed_item_id")} helperText={resource.data?.[0]?.map((item) => `${item.name}: ${item.id}`).join(" · ")} /><AppInput label="Group name" value={form.group_name} onChangeText={set("group_name")} /><AppInput label="Head count" value={form.head_count} onChangeText={set("head_count")} keyboardType="number-pad" /><AppInput label="Quantity per head" value={form.quantity_per_head} onChangeText={set("quantity_per_head")} keyboardType="decimal-pad" /><AppInput label="Feeding time" value={form.feeding_time} onChangeText={set("feeding_time")} /><AppInput label="Start date" value={form.start_date} onChangeText={set("start_date")} />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton title="Create Schedule" onPress={submit} /></View></AppCard> : null}<LoadState resource={{ ...resource, data: resource.data?.[1] }} emptyTitle="No feeding schedules" onRetry={resource.refresh}>{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={row.name} subtitle={`${row.group_name || row.cattle_id} · ${row.quantity_per_head} ${row.unit} per head at ${row.feeding_time}`} status={row.is_active ? "Active" : "Inactive"} />)}</View>}</LoadState></FeedPage>;
}

export function DailyFeedingRecordsScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id;
  const resource = useResource(() => Promise.all([api.listItems(farmId), api.listConsumption(farmId, { date_from: monthStart(), date_to: today() })]), [api, farmId]);
  const [form, setForm] = useState({ feed_item_id: "", group_name: "", head_count: "", quantity: "", feeding_date: today(), notes: "" }); const [feedback, setFeedback] = useState(null); const set = (key) => (value) => setForm((old) => ({ ...old, [key]: value })); const selected = resource.data?.[0]?.find((item) => item.id === form.feed_item_id);
  const submit = async () => { if (!selected || !form.group_name.trim() || Number(form.head_count) <= 0 || Number(form.quantity) <= 0) { setFeedback({ type: "error", message: "Select a feed item and enter a group, head count, and positive total quantity." }); return; } try { await api.createConsumption(farmId, { client_request_id: requestId(), feed_item_id: selected.id, target_type: "GROUP", group_name: form.group_name, head_count: Number(form.head_count), feeding_date: form.feeding_date, quantity: form.quantity, unit: selected.unit, notes: form.notes || null }); setFeedback({ type: "success", message: "Daily feeding recorded and inventory deducted." }); setForm({ ...form, quantity: "", notes: "" }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } };
  return <FeedPage title="Daily Feeding Records" subtitle="Each record is idempotent, audited, and atomically deducted from inventory." permission="feed.record" onBack={onBack}><AppCard title="Record Feeding"><View style={styles.form}><AppInput testID="feeding-item" label="Feed item ID" value={form.feed_item_id} onChangeText={set("feed_item_id")} helperText={resource.data?.[0]?.map((item) => `${item.name}: ${item.id}`).join(" · ")} /><AppInput label="Cattle group" value={form.group_name} onChangeText={set("group_name")} /><AppInput label="Head count" value={form.head_count} onChangeText={set("head_count")} keyboardType="number-pad" /><AppInput testID="feeding-quantity" label="Total quantity" value={form.quantity} onChangeText={set("quantity")} keyboardType="decimal-pad" /><AppInput label="Feeding date" value={form.feeding_date} onChangeText={set("feeding_date")} /><AppInput label="Notes" value={form.notes} onChangeText={set("notes")} multiline />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton testID="feeding-submit" title="Record Feeding" onPress={submit} /></View></AppCard><LoadState resource={{ ...resource, data: resource.data?.[1] }} emptyTitle="No feeding records this month" onRetry={resource.refresh}>{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={`${row.quantity} ${row.unit}`} subtitle={`${row.feeding_date} · ${row.group_name || row.cattle_id}`} />)}</View>}</LoadState></FeedPage>;
}

export function LowStockAlertsScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const resource = useResource(() => api.lowStock(farm.activeFarm?.id), [api, farm.activeFarm?.id]);
  return <FeedPage title="Low Stock Alerts" subtitle="Alerts appear when an active item reaches its configured reorder threshold." onBack={onBack}><LoadState resource={resource} emptyTitle="No low-stock alerts" onRetry={resource.refresh}>{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.feed_item_id} title={row.name} subtitle={`${row.current_quantity} ${row.unit} remaining · threshold ${row.reorder_level}`} status="Low stock" />)}</View>}</LoadState></FeedPage>;
}

export function NutritionPlansScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id; const canManage = farm.can("feed.nutrition.manage");
  const resource = useResource(() => Promise.all([api.listItems(farmId), api.listNutritionPlans(farmId)]), [api, farmId]);
  const [form, setForm] = useState({ name: "", objective: "", group_name: "", feed_item_id: "", quantity: "", start_date: today(), notes: "" }); const [feedback, setFeedback] = useState(null); const set = (key) => (value) => setForm((old) => ({ ...old, [key]: value })); const selected = resource.data?.[0]?.find((item) => item.id === form.feed_item_id);
  const submit = async () => { if (!selected || form.name.trim().length < 2 || form.objective.trim().length < 3 || !form.group_name.trim() || Number(form.quantity) <= 0) { setFeedback({ type: "error", message: "Complete the plan name, objective, target group, feed item, and positive daily quantity." }); return; } try { await api.createNutritionPlan(farmId, { name: form.name, objective: form.objective, notes: form.notes || null, target_type: "GROUP", group_name: form.group_name, start_date: form.start_date, lines: [{ feed_item_id: selected.id, daily_quantity_per_head: form.quantity, unit: selected.unit }] }); setFeedback({ type: "success", message: "Draft nutrition plan created for professional review." }); await resource.refresh(); } catch (error) { setFeedback({ type: "error", message: feedErrorMessage(error) }); } };
  return <FeedPage title="Nutrition Plans" subtitle="Plans are operational guidance and are never presented as automatically veterinarian-approved." permission="feed.nutrition.view" onBack={onBack}><InlineFeedback type="info" message="Nutrition estimates require qualified professional review where appropriate. A REVIEWED status records who reviewed the plan; it does not imply veterinary certification." />{canManage ? <AppCard title="Create Draft Plan"><View style={styles.form}><AppInput label="Plan name" value={form.name} onChangeText={set("name")} /><AppInput label="Objective" value={form.objective} onChangeText={set("objective")} /><AppInput label="Target group" value={form.group_name} onChangeText={set("group_name")} /><AppInput label="Feed item ID" value={form.feed_item_id} onChangeText={set("feed_item_id")} helperText={resource.data?.[0]?.map((item) => `${item.name}: ${item.id}`).join(" · ")} /><AppInput label="Daily quantity per head" value={form.quantity} onChangeText={set("quantity")} keyboardType="decimal-pad" /><AppInput label="Start date" value={form.start_date} onChangeText={set("start_date")} /><AppInput label="Notes" value={form.notes} onChangeText={set("notes")} multiline />{feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}<AppButton title="Create Draft Plan" onPress={submit} /></View></AppCard> : null}<LoadState resource={{ ...resource, data: resource.data?.[1] }} emptyTitle="No nutrition plans" onRetry={resource.refresh}>{(rows) => <View style={styles.form}>{rows.map((row) => <RecordCard key={row.id} title={row.name} subtitle={`${row.objective} · ${row.lines.length} feed item(s)`} status={row.status}><Text>{row.advisory}</Text>{canManage && row.status === "DRAFT" ? <AppButton title="Mark Reviewed" variant="outline" size="small" onPress={async () => { await api.updateNutritionPlan(farmId, row.id, { status: "REVIEWED" }); await resource.refresh(); }} /> : null}</RecordCard>)}</View>}</LoadState></FeedPage>;
}

export function FeedReportsScreen({ onBack, api = feedApi }) {
  const farm = useFarm(); const farmId = farm.activeFarm?.id; const canViewCosts = farm.can("feed.cost.view");
  const [range, setRange] = useState({ date_from: monthStart(), date_to: today() });
  const resource = useResource(async () => { const summary = await api.consumptionReport(farmId, range); const costs = canViewCosts ? await api.costReport(farmId, range) : null; return { summary, costs }; }, [api, farmId, range.date_from, range.date_to, canViewCosts]);
  return <FeedPage title="Feed Reports" subtitle="Consumption and purchasing are separated so financial data is not exposed through ordinary feed viewing." permission="feed.reports.view" onBack={onBack}><AppCard title="Report Range"><View style={styles.wrap}><AppInput label="From" value={range.date_from} onChangeText={(value) => setRange((old) => ({ ...old, date_from: value }))} style={styles.field} /><AppInput label="To" value={range.date_to} onChangeText={(value) => setRange((old) => ({ ...old, date_to: value }))} style={styles.field} /></View></AppCard>{resource.status === "loading" ? <FeedbackState type="loading" title="Calculating feed report" showSkeleton /> : null}{resource.status === "error" ? <FeedbackState type="error" title="Report unavailable" message={feedErrorMessage(resource.error)} actionLabel="Retry" onAction={resource.refresh} /> : null}{resource.status === "ready" ? <View style={styles.form}><AppCard title="Consumption"><Text>{resource.data.summary.consumption_records} feeding records</Text>{Object.entries(resource.data.summary.consumption_quantity_by_unit).map(([unit, value]) => <Text key={unit}>{value} {unit}</Text>)}</AppCard>{resource.data.costs ? <AppCard title="Purchasing Costs"><Text>{resource.data.costs.purchase_count} purchases</Text>{Object.entries(resource.data.costs.purchase_cost_by_currency).map(([currency, value]) => <Text key={currency}>{value} {currency}</Text>)}</AppCard> : <InlineFeedback type="info" message="Financial cost analytics require feed.cost.view permission." />}</View> : null}</FeedPage>;
}

const styles = StyleSheet.create({
  page: { width: "100%", alignSelf: "center", paddingBottom: 48 },
  headingRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  grow: { flex: 1 },
  wrap: { flexDirection: "row", flexWrap: "wrap", alignItems: "flex-end" },
  form: { gap: 12 },
  stat: { minWidth: 170, flexGrow: 1 },
  field: { minWidth: 190, flexGrow: 1 },
});
