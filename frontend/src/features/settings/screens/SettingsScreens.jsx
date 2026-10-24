import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { authApi } from "../../../api/auth";
import { settingsApi } from "../../../api/settings";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { ConfirmationDialog } from "../../../components/ui/ConfirmationDialog";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAuth } from "../../auth/context/AuthProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { useAppTheme } from "../../../theme/ThemeProvider";

const errorText = (error) => error?.body?.detail || error?.message || "The request could not be completed.";
const preferencePayload = (value) => ({ phone: value?.phone || null, language: value?.language || "en", timezone: value?.timezone || "UTC", date_format: value?.date_format || "YYYY-MM-DD", time_format: value?.time_format || "24H", theme: value?.theme || "emerald" });
const farmPreferencePayload = (value) => ({ contact_email: value?.contact_email || null, contact_phone: value?.contact_phone || null, address: value?.address || null, timezone: value?.timezone || "UTC", measurement_system: value?.measurement_system || "METRIC", milk_volume_unit: value?.milk_volume_unit || "LITER", feed_weight_unit: value?.feed_weight_unit || "KG", notification_settings: value?.notification_settings || {}, operational_settings: value?.operational_settings || {} });

function Page({ title, subtitle, children }) {
  const { theme, spacing, typography, layout } = useAppTheme();
  return <Screen><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.page, { maxWidth: layout.contentMaxWidth, padding: spacing.lg, gap: spacing.lg }]}><View><Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>{title}</Text><Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{subtitle}</Text></View>{children}</ScrollView></Screen>;
}

const SETTINGS_LINKS = [
  ["Personal Profile", "/settings/profile", "Name, contact details and existing avatar tools"],
  ["Account Security", "/settings/security", "Password, verified email, sessions and security history"],
  ["Appearance & Theme", "/settings/appearance", "Emerald, Midnight Teal or Royal Indigo"],
  ["Notification Preferences", "/notifications/preferences", "Supported in-app, email and push preferences"],
  ["Farm Profile & Configuration", "/settings/farm", "Farm-scoped operational and unit preferences"],
  ["Farm Staff & Permissions", "/farm/staff", "Authorized memberships and worker assignments"],
  ["Invitations", "/farm/staff/invite", "Invite Workers and Veterinarians"],
  ["Account Management", "/settings/account", "Deactivation and deletion-review workflow"],
  ["Farm Administration", "/farm/details", "Farm ownership and status overview"],
];

export function SettingsHomeScreen() {
  const router = useRouter(); const auth = useAuth();
  const links = auth.user?.is_system_admin ? [...SETTINGS_LINKS, ["Platform Backup & Recovery", "/admin/backups", "Encrypted platform backups for System Admin only"]] : SETTINGS_LINKS;
  return <Page title="Settings" subtitle="Personal, security and active-farm configuration."><View style={styles.grid}>{links.map(([title, href, subtitle]) => <AppCard key={href} title={title} subtitle={subtitle} onPress={() => router.push(href)} style={styles.tile} />)}</View></Page>;
}

export function PersonalSettingsScreen() {
  const auth = useAuth(); const router = useRouter(); const [name, setName] = useState(auth.user?.full_name || ""); const [phone, setPhone] = useState(""); const [prefs, setPrefs] = useState(null); const [issue, setIssue] = useState(null); const [saving, setSaving] = useState(false);
  useEffect(() => { authApi.getPreferences().then((x) => { setPrefs(x); setPhone(x.phone || ""); }).catch((e) => setIssue(errorText(e))); }, []);
  const save = async () => { setSaving(true); setIssue(null); try { await authApi.updateProfile({ full_name: name.trim() }); await authApi.updatePreferences({ ...preferencePayload(prefs), phone: phone.trim() || null }); await auth.refreshProfile(); setIssue("Profile settings saved."); } catch (e) { setIssue(errorText(e)); } finally { setSaving(false); } };
  return <Page title="Personal profile" subtitle="Your email remains unchanged until a new address is verified.">{issue ? <InlineFeedback message={issue} /> : null}<AppCard><View style={styles.stack}><AppInput label="Full name" required value={name} onChangeText={setName} maxLength={120} /><AppInput label="Contact phone" value={phone} onChangeText={setPhone} maxLength={32} /><AppInput label="Verified email" disabled value={auth.user?.email || ""} /><Text>Account created: {auth.user?.created_at ? new Date(auth.user.created_at).toLocaleString() : "Unavailable"}</Text><AppButton title="Save profile" loading={saving} onPress={() => void save()} /><AppButton title="Manage profile picture" variant="outline" onPress={() => router.push("/profile")} /></View></AppCard></Page>;
}

export function SecuritySettingsScreen() {
  const auth = useAuth(); const [form, setForm] = useState({ current_password: "", new_password: "" }); const [email, setEmail] = useState(""); const [issue, setIssue] = useState(null); const [events, setEvents] = useState([]);
  const load = () => authApi.securityEvents().then(setEvents).catch((e) => setIssue(errorText(e))); useEffect(load, []);
  const run = async (fn, success) => { setIssue(null); try { await fn(); setIssue(success); } catch (e) { setIssue(errorText(e)); } };
  return <Page title="Account security" subtitle="Sensitive changes require your current password and invalidate existing tokens where applicable.">{issue ? <InlineFeedback message={issue} /> : null}<AppCard title="Change password"><View style={styles.stack}><AppInput label="Current password" secureTextEntry value={form.current_password} onChangeText={(v) => setForm({ ...form, current_password: v })} /><AppInput label="New password" secureTextEntry helperText="Use at least 12 characters with upper/lowercase, number and symbol." value={form.new_password} onChangeText={(v) => setForm({ ...form, new_password: v })} /><AppButton title="Change password" onPress={() => void run(() => authApi.changePassword(form), "Password changed. Sign in again on all devices.")} /></View></AppCard><AppCard title="Change verified email"><View style={styles.stack}><AppInput label="New email" keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail} /><AppInput label="Current password" secureTextEntry value={form.current_password} onChangeText={(v) => setForm({ ...form, current_password: v })} /><AppButton title="Send verification" onPress={() => void run(() => authApi.requestEmailChange({ new_email: email.trim(), current_password: form.current_password }), "Verification sent to the new address.")} /></View></AppCard><AppCard title="Sessions" subtitle="JWT sessions are stateless; revocation invalidates all issued access tokens, including this one."><AppButton title="Revoke all sessions" variant="outline" onPress={() => void run(() => authApi.revokeSessions({ current_password: form.current_password }), "Sessions revoked. Please sign in again.")} /></AppCard><AppCard title="Security events">{events.length ? events.map((x) => <Text key={x.id}>{x.summary} · {new Date(x.created_at).toLocaleString()}</Text>) : <Text>No security events recorded.</Text>}</AppCard></Page>;
}

export function AppearanceSettingsScreen() {
  const { themeId, themes, changeTheme } = useAppTheme(); const [issue, setIssue] = useState(null);
  const choose = async (id) => { try { await changeTheme(id); const current = await authApi.getPreferences(); await authApi.updatePreferences({ ...preferencePayload(current), theme: id }); setIssue("Theme saved on this device and account."); } catch (e) { setIssue(errorText(e)); } };
  return <Page title="Appearance & theme" subtitle="Choose one of the three existing ICMS themes.">{issue ? <InlineFeedback message={issue} /> : null}<View style={styles.grid}>{Object.entries(themes).map(([id, item]) => <AppCard key={id} title={item.name || id} subtitle={themeId === id ? "Active" : "Tap to apply"} onPress={() => void choose(id)} style={styles.tile} />)}</View></Page>;
}

export function FarmSettingsScreen() {
  const farm = useFarm(); const [data, setData] = useState(null); const [issue, setIssue] = useState(null);
  useEffect(() => { if (farm.activeFarm?.id) settingsApi.getFarm(farm.activeFarm.id).then(setData).catch((e) => setIssue(errorText(e))); }, [farm.activeFarm?.id]);
  if (!farm.activeFarm) return <Page title="Farm configuration" subtitle="Select an active farm first."><FeedbackState title="No active farm" /></Page>;
  if (!data) return <Page title="Farm configuration" subtitle={farm.activeFarm.name}>{issue ? <FeedbackState type="error" title="Settings unavailable" message={issue} /> : <FeedbackState type="loading" title="Loading settings" />}</Page>;
  const save = async () => { setIssue(null); try { setData(await settingsApi.updateFarm(farm.activeFarm.id, farmPreferencePayload(data))); setIssue("Farm settings saved."); } catch (e) { setIssue(errorText(e)); } };
  return <Page title="Farm profile & configuration" subtitle={`${farm.activeFarm.name} · ${farm.membership?.role || "member"}`}>{issue ? <InlineFeedback message={issue} /> : null}<AppCard><View style={styles.stack}><AppInput label="Contact email" value={data.contact_email || ""} onChangeText={(v) => setData({ ...data, contact_email: v || null })} /><AppInput label="Contact phone" value={data.contact_phone || ""} onChangeText={(v) => setData({ ...data, contact_phone: v || null })} /><AppInput label="Address / location" multiline value={data.address || ""} onChangeText={(v) => setData({ ...data, address: v || null })} /><AppInput label="Timezone" value={data.timezone} onChangeText={(v) => setData({ ...data, timezone: v })} /><Text>Measurement system: {data.measurement_system}</Text><Text>Milk unit: {data.milk_volume_unit} · Feed unit: {data.feed_weight_unit}</Text><AppButton title="Save farm configuration" disabled={!farm.can("farm.manage")} onPress={() => void save()} /></View></AppCard></Page>;
}

export function AccountManagementScreen() {
  const [password, setPassword] = useState(""); const [reason, setReason] = useState(""); const [issue, setIssue] = useState(null); const [confirmation, setConfirmation] = useState(null); const [pending, setPending] = useState(false);
  const run = async (fn) => { try { const out = await fn(); setIssue(out.detail); } catch (e) { setIssue(errorText(e)); } };
  const confirm = async () => { const selected = confirmation; setPending(true); await run(() => selected === "deactivate" ? authApi.deactivate({ current_password: password }) : authApi.requestDeletion({ current_password: password, reason: reason || null })); setPending(false); setConfirmation(null); };
  return <Page title="Account management" subtitle="These actions never silently delete farms, financial records or audit history.">{issue ? <InlineFeedback message={issue} /> : null}<AppCard><View style={styles.stack}><AppInput label="Current password" secureTextEntry value={password} onChangeText={setPassword} /><AppButton title="Deactivate my account" variant="danger" onPress={() => setConfirmation("deactivate")} /></View></AppCard><AppCard title="Deletion request" subtitle="Submits a review request; it does not immediately erase records."><View style={styles.stack}><AppInput label="Reason (optional)" multiline value={reason} onChangeText={setReason} /><AppButton title="Request deletion review" variant="danger" onPress={() => setConfirmation("delete")} /></View></AppCard><ConfirmationDialog visible={Boolean(confirmation)} title={confirmation === "deactivate" ? "Deactivate account?" : "Submit deletion request?"} message={confirmation === "deactivate" ? "You will lose access. Active farm owners must transfer ownership first." : "This starts a review and does not immediately erase protected business or audit records."} confirmLabel={confirmation === "deactivate" ? "Deactivate" : "Submit request"} destructive pending={pending} onCancel={() => setConfirmation(null)} onConfirm={() => void confirm()} /></Page>;
}

const styles = StyleSheet.create({ page: { width: "100%", alignSelf: "center" }, stack: { gap: 14 }, grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 }, tile: { minWidth: 250, flex: 1 } });
