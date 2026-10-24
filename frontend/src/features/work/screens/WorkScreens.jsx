import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { workApi } from "../../../api/work";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { StatCard } from "../../../components/ui/StatCard";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission, useCan } from "../../permissions/guards";
import { useAppTheme } from "../../../theme/ThemeProvider";

const uuid = () => "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => { const r = Math.floor(Math.random() * 16); return (c === "x" ? r : (r & 3) | 8).toString(16); });
const errorText = (error) => error?.body?.detail || error?.message || "The request could not be completed.";

function Page({ title, subtitle, permission = "task.view", children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return <Screen><RequireFarm><RequirePermission permission={permission}><ScrollView contentContainerStyle={[styles.page, { maxWidth: layout.contentMaxWidth, padding: spacing.lg, gap: spacing.lg }]}><View><Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>{title}</Text><Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text></View>{children}</ScrollView></RequirePermission></RequireFarm></Screen>;
}

function useLoad(loader, dependencies) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const refresh = useCallback(async () => { setState((x) => ({ ...x, loading: true, error: null })); try { const data = await loader(); setState({ loading: false, data, error: null }); return data; } catch (error) { setState({ loading: false, data: null, error }); return null; } }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void refresh(); }, [refresh]);
  return { ...state, refresh };
}

function TaskCard({ task, onOpen, showActions = false, api = workApi, refresh }) {
  const farmId = useFarm().activeFarm?.id;
  const { theme, spacing, typography } = useAppTheme();
  const overdue = task.is_overdue;
  const setStatus = async (next) => { await api.updateStatus(farmId, task.id, { status: next, expected_version: task.version }); await refresh?.(); };
  return <AppCard><Pressable accessibilityRole="button" onPress={() => onOpen?.(task.id)}><View style={styles.row}><View style={styles.grow}><Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>{task.title}</Text><Text style={{ color: theme.colors.textSecondary, marginTop: 4 }}>{task.category} · {task.due_at ? new Date(task.due_at).toLocaleString() : "No due date"}</Text></View><StatusBadge label={overdue ? "OVERDUE" : task.status} status={overdue ? "error" : task.status === "COMPLETED" ? "success" : "info"} compact /></View></Pressable>{showActions && task.status === "OPEN" ? <View style={[styles.row, { marginTop: spacing.md }]}><AppButton title="Start" size="small" fullWidth={false} onPress={() => void setStatus("IN_PROGRESS")} /><AppButton title="Complete" size="small" variant="outline" fullWidth={false} onPress={() => void setStatus("COMPLETED")} /></View> : null}</AppCard>;
}

function TaskList({ mine = false, onOpen, api = workApi, actions = false }) {
  const farmId = useFarm().activeFarm?.id;
  const state = useLoad(() => api.listTasks(farmId, mine ? { mine: true } : undefined), [api, farmId, mine]);
  if (state.loading) return <FeedbackState type="loading" title="Loading tasks" showSkeleton />;
  if (state.error) return <FeedbackState type="error" title="Tasks unavailable" message={errorText(state.error)} actionLabel="Retry" onAction={state.refresh} />;
  if (!state.data?.length) return <FeedbackState title="No tasks" message="No matching farm tasks are available." />;
  return <View style={styles.stack}>{state.data.map((task) => <TaskCard key={task.id} task={task} onOpen={onOpen} showActions={actions} api={api} refresh={state.refresh} />)}</View>;
}

function TaskOverview({ mine, api }) {
  const farmId = useFarm().activeFarm?.id;
  const state = useLoad(() => api.listTasks(farmId, mine ? { mine: true } : undefined), [api, farmId, mine]);
  if (state.loading) return <FeedbackState type="loading" title="Loading task summary" showSkeleton />;
  if (state.error) return <FeedbackState type="error" title="Task summary unavailable" message={errorText(state.error)} actionLabel="Retry" onAction={state.refresh} />;
  const rows = state.data || []; const now = new Date();
  const stats = [
    ["Open", rows.filter((x) => x.status === "OPEN").length, "info"],
    ["In progress", rows.filter((x) => x.status === "IN_PROGRESS").length, "warning"],
    ["Overdue", rows.filter((x) => x.is_overdue || (x.due_at && new Date(x.due_at) < now && !["COMPLETED", "CANCELLED"].includes(x.status))).length, "error"],
    ["Completed", rows.filter((x) => x.status === "COMPLETED").length, "success"],
  ];
  return <View style={styles.grid}>{stats.map(([label, value, status]) => <StatCard key={label} label={label} value={value} status={status} style={{ minWidth: 150, flexGrow: 1 }} />)}</View>;
}

const LINKS = [
  ["My Tasks", "/tasks/my"], ["Farm Tasks", "/tasks/farm"], ["Create Task", "/tasks/create"], ["Assigned Cattle", "/tasks/assigned-cattle"],
  ["Worker Assignments", "/tasks/worker-assignments"], ["Veterinary Tasks", "/tasks/veterinary"], ["Reminders", "/tasks/reminders"],
  ["Notifications", "/notifications"], ["Preferences", "/notifications/preferences"], ["Task Reports", "/tasks/reports"],
];

export function TasksDashboardScreen({ onNavigate, api = workApi }) {
  const canManage = useCan("task.manage");
  return <Page title="Tasks & Notifications" subtitle="Farm work, assigned cattle and time-sensitive reminders."><TaskOverview mine={!canManage} api={api} /><View style={styles.grid}>{LINKS.filter(([label]) => canManage || !["Farm Tasks", "Create Task", "Worker Assignments", "Task Reports"].includes(label)).map(([label, route]) => <AppCard key={route}><Pressable accessibilityRole="link" onPress={() => onNavigate(route)}><Text style={styles.link}>{label} →</Text></Pressable></AppCard>)}</View><TaskList mine={!canManage} onOpen={(id) => onNavigate(`/tasks/${id}`)} actions={!canManage} api={api} /></Page>;
}

export function CreateTaskScreen({ onDone, api = workApi }) {
  const farmId = useFarm().activeFarm?.id; const [form, setForm] = useState({ title: "", description: "", due_at: "", assignee_ids: "" }); const [issue, setIssue] = useState(null); const [saving, setSaving] = useState(false);
  const save = async () => { if (!form.title.trim()) return setIssue("Title is required."); setSaving(true); setIssue(null); try { const item = await api.createTask(farmId, { title: form.title.trim(), description: form.description.trim() || null, category: "GENERAL", priority: "MEDIUM", due_at: form.due_at ? new Date(form.due_at).toISOString() : null, assignee_ids: form.assignee_ids.split(",").map((x) => x.trim()).filter(Boolean), recurrence_kind: "NONE", recurrence_interval: 1, recurrence_until: null, client_request_id: uuid() }); onDone(item.id); } catch (error) { setIssue(errorText(error)); } finally { setSaving(false); } };
  return <Page title="Create task" subtitle="Create farm-scoped work and optionally assign active members." permission="task.manage">{issue ? <InlineFeedback type="error" message={issue} /> : null}<AppCard><View style={styles.stack}><AppInput label="Title" value={form.title} onChangeText={(title) => setForm({ ...form, title })} /><AppInput label="Description" value={form.description} onChangeText={(description) => setForm({ ...form, description })} multiline /><AppInput label="Due date and time" placeholder="2026-10-25T09:00:00+05:00" value={form.due_at} onChangeText={(due_at) => setForm({ ...form, due_at })} /><AppInput label="Assignee user IDs" helperText="Comma-separated active farm member IDs" value={form.assignee_ids} onChangeText={(assignee_ids) => setForm({ ...form, assignee_ids })} /><AppButton title={saving ? "Creating…" : "Create task"} disabled={saving} onPress={() => void save()} /></View></AppCard></Page>;
}

export function TaskDetailScreen({ taskId, onEdit, api = workApi }) {
  const farmId = useFarm().activeFarm?.id; const canManage = useCan("task.manage"); const state = useLoad(() => api.getTask(farmId, taskId), [api, farmId, taskId]);
  if (state.loading) return <Page title="Task" subtitle="Loading task details"><FeedbackState type="loading" title="Loading task" /></Page>;
  if (state.error) return <Page title="Task" subtitle="Task details"><FeedbackState type="error" title="Task unavailable" message={errorText(state.error)} /></Page>;
  const task = state.data; return <Page title={task.title} subtitle="Task details and current assignment"><TaskCard task={task} showActions={!canManage} api={api} refresh={state.refresh} /><AppCard><Text>Description: {task.description || "None"}</Text><Text>Priority: {task.priority}</Text><Text>Assignees: {task.assignee_ids?.join(", ") || "Unassigned"}</Text></AppCard>{canManage && onEdit ? <AppButton title="Edit or reassign" variant="outline" onPress={onEdit} /> : null}</Page>;
}

export function EditTaskScreen({ taskId, onDone, api = workApi }) {
  const farmId = useFarm().activeFarm?.id; const state = useLoad(() => api.getTask(farmId, taskId), [api, farmId, taskId]); const [title, setTitle] = useState(""); const [assignees, setAssignees] = useState(""); const [issue, setIssue] = useState(null);
  useEffect(() => { if (state.data) { setTitle(state.data.title); setAssignees(state.data.assignee_ids?.join(", ") || ""); } }, [state.data]);
  const save = async () => { try { const updated = await api.updateTask(farmId, taskId, { title, expected_version: state.data.version }); await api.assignTask(farmId, taskId, { assignee_ids: assignees.split(",").map((x) => x.trim()).filter(Boolean) }); onDone(updated.id); } catch (error) { setIssue(errorText(error)); } };
  return <Page title="Edit or reassign" subtitle="Optimistic concurrency prevents lost updates." permission="task.manage">{state.loading ? <FeedbackState type="loading" title="Loading task" /> : <AppCard><View style={styles.stack}>{issue ? <InlineFeedback type="error" message={issue} /> : null}<AppInput label="Title" value={title} onChangeText={setTitle} /><AppInput label="Assignee user IDs" value={assignees} onChangeText={setAssignees} /><AppButton title="Save changes" onPress={() => void save()} /></View></AppCard>}</Page>;
}

export const MyTasksScreen = ({ onOpen, api = workApi }) => <Page title="My tasks" subtitle="Tasks currently assigned to you."><TaskList mine actions onOpen={onOpen} api={api} /></Page>;
export const FarmTasksScreen = ({ onOpen, api = workApi }) => <Page title="Farm tasks" subtitle="All operational work for this farm." permission="task.manage"><TaskList onOpen={onOpen} api={api} /></Page>;
export const VeterinaryTasksScreen = ({ onOpen, api = workApi }) => <Page title="Veterinary task dashboard" subtitle="Assigned clinical and animal-care work; financial data is not exposed."><TaskList mine actions onOpen={onOpen} api={api} /></Page>;

export function AssignedCattleScreen({ api = workApi }) { const farmId = useFarm().activeFarm?.id; const state = useLoad(() => api.listCattleAssignments(farmId), [api, farmId]); return <Page title="Assigned cattle" subtitle="Animals explicitly assigned to your care.">{state.loading ? <FeedbackState type="loading" title="Loading assignments" /> : state.error ? <FeedbackState type="error" title="Assignments unavailable" message={errorText(state.error)} /> : !state.data?.length ? <FeedbackState title="No assigned cattle" message="No active cattle assignments were found." /> : state.data.map((x) => <AppCard key={x.id}><Text>Cattle: {x.cattle_id}</Text><Text>Assigned: {new Date(x.assigned_at).toLocaleDateString()}</Text></AppCard>)}</Page>; }

export function WorkerAssignmentScreen({ api = workApi }) { const farmId = useFarm().activeFarm?.id; const [worker, setWorker] = useState(""); const [cattle, setCattle] = useState(""); const [issue, setIssue] = useState(null); const save = async () => { try { await api.assignCattle(farmId, { worker_id: worker.trim(), cattle_id: cattle.trim() }); setWorker(""); setCattle(""); setIssue("Assignment saved."); } catch (error) { setIssue(errorText(error)); } }; return <Page title="Worker-to-cattle assignments" subtitle="Farm managers control explicit animal responsibility." permission="cattle.assignment.manage"><AppCard><View style={styles.stack}>{issue ? <InlineFeedback message={issue} /> : null}<AppInput label="Worker user ID" value={worker} onChangeText={setWorker} /><AppInput label="Cattle ID" value={cattle} onChangeText={setCattle} /><AppButton title="Assign cattle" onPress={() => void save()} /></View></AppCard></Page>; }

export function ReminderListScreen({ onOpen }) { const farmId = useFarm().activeFarm?.id; const state = useLoad(() => workApi.listTasks(farmId), [farmId]); const items = useMemo(() => (state.data || []).filter((x) => x.due_at && !["COMPLETED", "CANCELLED"].includes(x.status)).sort((a, b) => new Date(a.due_at) - new Date(b.due_at)), [state.data]); return <Page title="Reminder calendar" subtitle="Upcoming and overdue authoritative task due dates.">{state.loading ? <FeedbackState type="loading" title="Loading reminders" /> : !items.length ? <FeedbackState title="No reminders" message="No due tasks are scheduled." /> : items.map((x) => <TaskCard key={x.id} task={x} onOpen={onOpen} />)}</Page>; }

export function NotificationInboxScreen({ onOpen, api = workApi }) { const farmId = useFarm().activeFarm?.id; const state = useLoad(() => api.notifications({ farm_id: farmId }), [api, farmId]); return <Page title="Notifications" subtitle="Your private in-app inbox for the active farm.">{state.loading ? <FeedbackState type="loading" title="Loading notifications" /> : state.error ? <FeedbackState type="error" title="Inbox unavailable" message={errorText(state.error)} /> : <View style={styles.stack}><AppButton title={`Mark all read (${state.data?.unread || 0} unread)`} variant="outline" onPress={async () => { await api.markAllRead({ query: { farm_id: farmId } }); await state.refresh(); }} />{state.data?.items?.map((item) => <AppCard key={item.id}><Pressable onPress={() => onOpen(item.id)}><Text style={styles.link}>{item.title}{item.read_at ? "" : " •"}</Text><Text>{item.message}</Text></Pressable></AppCard>)}</View>}</Page>; }

export function NotificationDetailScreen({ notificationId, api = workApi }) { const state = useLoad(async () => { const item = await api.getNotification(notificationId); if (item && !item.read_at) return api.markRead(item.id); return item; }, [api, notificationId]); return <Page title="Notification" subtitle="Notification details">{state.loading ? <FeedbackState type="loading" title="Loading notification" /> : !state.data ? <FeedbackState type="error" title="Notification not found" /> : <AppCard><Text style={styles.link}>{state.data.title}</Text><Text>{state.data.message}</Text><Text>{new Date(state.data.created_at).toLocaleString()}</Text></AppCard>}</Page>; }

export function NotificationPreferencesScreen({ api = workApi }) { const state = useLoad(() => api.getPreferences(), [api]); const [message, setMessage] = useState(null); const toggle = async (key) => { const next = { ...state.data, [key]: !state.data[key] }; delete next.user_id; delete next.updated_at; await api.updatePreferences(next); await state.refresh(); setMessage("Preferences saved."); }; return <Page title="Notification preferences" subtitle="External email and push remain off until configured and approved.">{state.loading ? <FeedbackState type="loading" title="Loading preferences" /> : <View style={styles.stack}>{message ? <InlineFeedback message={message} /> : null}{[["in_app_enabled", "In-app"], ["email_enabled", "Email"], ["push_enabled", "Push"]].map(([key, label]) => <AppCard key={key}><View style={styles.row}><Text style={styles.grow}>{label}: {state.data[key] ? "Enabled" : "Disabled"}</Text><AppButton title="Toggle" size="small" fullWidth={false} onPress={() => void toggle(key)} /></View></AppCard>)}</View>}</Page>; }

export function TaskHistoryReportsScreen() { const farmId = useFarm().activeFarm?.id; const state = useLoad(() => workApi.listTasks(farmId), [farmId]); const counts = useMemo(() => (state.data || []).reduce((out, x) => ({ ...out, [x.status]: (out[x.status] || 0) + 1 }), {}), [state.data]); return <Page title="Task history & reports" subtitle="Operational status summary; no financial data is included." permission="task.manage">{state.loading ? <FeedbackState type="loading" title="Loading report" /> : <View style={styles.grid}>{Object.entries(counts).map(([key, value]) => <AppCard key={key}><Text style={styles.link}>{value}</Text><Text>{key}</Text></AppCard>)}</View>}</Page>; }

const styles = StyleSheet.create({ page: { width: "100%", alignSelf: "center" }, stack: { gap: 12 }, row: { flexDirection: "row", alignItems: "center", gap: 10 }, grow: { flex: 1 }, grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 }, link: { color: "#087F8C", fontWeight: "700", fontSize: 16 } });
