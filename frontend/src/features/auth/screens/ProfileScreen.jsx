import { ScrollView, StyleSheet, Text, View } from "react-native";

import { BrandMark } from "../../../components/brand/BrandMark";
import { AppButton } from "../../../components/ui/AppButton";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuth } from "../context/AuthProvider";

function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "IC";
}

function readableDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleDateString();
}

export function ProfileScreen({ onVerify }) {
  const { theme, spacing, radius, shadows, typography, layout } = useAppTheme();
  const { user, refreshProfile, isProfileRefreshing, logout } = useAuth();

  const runSafely = (action) => { void action().catch(() => {}); };
  if (!user) {
    return (
      <Screen style={{ backgroundColor: theme.colors.background }}>
        <View style={[styles.centered, { padding: spacing.xl, maxWidth: layout.formMaxWidth }]}>
          <FeedbackState type="loading" title="Loading profile" message="ICMS is confirming your account information." />
        </View>
      </Screen>
    );
  }

  const active = user.status.toUpperCase() === "ACTIVE";
  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <ScrollView contentContainerStyle={[styles.container, { padding: spacing.xl, maxWidth: layout.formMaxWidth }]}>
        <BrandMark size={52} showWordmark />
        <View style={[styles.card, shadows.large, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: spacing.xl, marginTop: spacing.xl }]}>
          <View style={[styles.avatar, { backgroundColor: theme.colors.primary, borderRadius: radius.pill }]} accessibilityLabel={`Profile initials ${initials(user.full_name)}`}>
            <Text style={[styles.avatarText, { color: theme.colors.onPrimary }]}>{initials(user.full_name)}</Text>
          </View>
          <Text accessibilityRole="header" style={[styles.name, { color: theme.colors.text, fontSize: typography.sizes.heading, marginTop: spacing.md }]}>{user.full_name}</Text>
          <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{user.email}</Text>
          <View style={[styles.badges, { marginTop: spacing.lg }]}>
            <StatusBadge status={user.is_email_verified ? "success" : "warning"} label={user.is_email_verified ? "Email verified" : "Email verification needed"} />
            <StatusBadge status={active ? "active" : "error"} label={active ? "Active account" : "Inactive account"} />
          </View>
        </View>
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: spacing.xl, marginTop: spacing.lg }]}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text }]}>Account information</Text>
          <ProfileRow label="Email address" value={user.email} theme={theme} spacing={spacing} />
          <ProfileRow label="Created" value={readableDate(user.created_at)} theme={theme} spacing={spacing} />
          <ProfileRow label="Account ID" value={user.id} theme={theme} spacing={spacing} selectable />
          <Text style={[styles.support, { color: theme.colors.textSecondary, marginTop: spacing.lg }]}>Profile editing and password changes are unavailable because the current backend exposes no supported account-update endpoint.</Text>
        </View>
        {!user.is_email_verified ? <AppButton title="Verify Email" onPress={onVerify} style={{ marginTop: spacing.lg }} /> : null}
        <AppButton title="Refresh Profile" variant="outline" loading={isProfileRefreshing} disabled={isProfileRefreshing} onPress={() => runSafely(refreshProfile)} style={{ marginTop: spacing.md }} testID="profile-refresh" />
        <AppButton title="Log Out" variant="outline" onPress={() => runSafely(logout)} style={{ marginTop: spacing.md }} testID="profile-logout" />
      </ScrollView>
    </Screen>
  );
}

function ProfileRow({ label, value, theme, spacing, selectable = false }) {
  return (
    <View style={[styles.row, { borderTopColor: theme.colors.border, marginTop: spacing.md, paddingTop: spacing.md }]}>
      <Text style={{ color: theme.colors.textSecondary, fontSize: 13 }}>{label}</Text>
      <Text selectable={selectable} style={{ color: theme.colors.text, fontSize: 14, fontWeight: "600", marginTop: 3 }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: "100%", alignSelf: "center", flexGrow: 1 },
  centered: { width: "100%", flex: 1, alignSelf: "center", justifyContent: "center" },
  card: { borderWidth: 1 },
  avatar: { alignItems: "center", height: 68, justifyContent: "center", width: 68 },
  avatarText: { fontSize: 23, fontWeight: "800" },
  name: { fontWeight: "800" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "800" },
  row: { borderTopWidth: 1 },
  support: { fontSize: 12, lineHeight: 18 },
});
