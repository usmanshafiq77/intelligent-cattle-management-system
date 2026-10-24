import { useCallback, useEffect, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";

import { authApi } from "../../../api/auth";
import { BrandMark } from "../../../components/brand/BrandMark";
import { AppButton } from "../../../components/ui/AppButton";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
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

function blobToDataUrl(blob) {
  if (typeof blob === "string") return Promise.resolve(blob);
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not display the profile image."));
    reader.onload = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}

async function pickedAssetBody(asset) {
  if (asset.file) return asset.file;
  const response = await fetch(asset.uri);
  if (!response.ok) throw new Error("Could not read the selected image.");
  return response.blob();
}

export function ProfileScreen({ onVerify, onSettings, avatarApi = authApi, imagePicker = ImagePicker }) {
  const { theme, spacing, radius, shadows, typography, layout } = useAppTheme();
  const { user, refreshProfile, isProfileRefreshing, logout } = useAuth();
  const [avatarUri, setAvatarUri] = useState(null);
  const [avatarLoading, setAvatarLoading] = useState(true);
  const [avatarPending, setAvatarPending] = useState(false);
  const [avatarFeedback, setAvatarFeedback] = useState(null);

  const loadAvatar = useCallback(async () => {
    if (!user) return;
    setAvatarLoading(true);
    try {
      setAvatarUri(await blobToDataUrl(await avatarApi.getAvatar()));
    } catch (error) {
      setAvatarUri(null);
      if (error?.status !== 404) setAvatarFeedback({ type: "error", message: "The profile picture could not be loaded." });
    } finally {
      setAvatarLoading(false);
    }
  }, [avatarApi, user?.id]);

  useEffect(() => { void loadAvatar(); }, [loadAvatar]);

  const selectAndUploadAvatar = async () => {
    setAvatarFeedback(null);
    let result;
    try {
      result = await imagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsEditing: true, aspect: [1, 1], quality: 0.85 });
    } catch {
      setAvatarFeedback({ type: "error", message: "The image gallery could not be opened." });
      return;
    }
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    setAvatarPending(true);
    try {
      const body = await pickedAssetBody(asset);
      await avatarApi.uploadAvatar(body, asset.mimeType || body.type || "application/octet-stream");
      await loadAvatar();
      setAvatarFeedback({ type: "success", message: "Profile picture updated." });
    } catch (error) {
      const message = error?.status === 413
        ? "The selected image is larger than 5 MB."
        : error?.status === 422
          ? "Choose a valid JPEG, PNG, or WebP image."
          : "The profile picture could not be uploaded. Please try again.";
      setAvatarFeedback({ type: "error", message });
    } finally {
      setAvatarPending(false);
    }
  };

  const removeAvatar = async () => {
    setAvatarPending(true);
    setAvatarFeedback(null);
    try {
      await avatarApi.removeAvatar();
      setAvatarUri(null);
      setAvatarFeedback({ type: "success", message: "Profile picture removed." });
    } catch {
      setAvatarFeedback({ type: "error", message: "The profile picture could not be removed. Please try again." });
    } finally {
      setAvatarPending(false);
    }
  };

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
          <View style={[styles.avatar, { backgroundColor: theme.colors.primary, borderRadius: radius.pill }]} accessibilityLabel={avatarUri ? "Current profile picture" : `Default profile avatar for ${user.full_name}`}>
            {avatarUri ? <Image testID="profile-avatar-image" source={{ uri: avatarUri }} style={styles.avatarImage} accessibilityLabel="Current profile picture" /> : <Text testID="profile-avatar-default" style={[styles.avatarText, { color: theme.colors.onPrimary }]}>{avatarLoading ? "…" : initials(user.full_name)}</Text>}
          </View>
          <View style={[styles.avatarActions, { marginTop: spacing.md }]}>
            <AppButton testID="profile-avatar-select" title={avatarUri ? "Replace Picture" : "Select Picture"} accessibilityLabel={avatarUri ? "Replace profile picture" : "Select profile picture"} size="small" fullWidth={false} loading={avatarPending} disabled={avatarPending} onPress={() => { void selectAndUploadAvatar(); }} />
            {avatarUri ? <AppButton testID="profile-avatar-remove" title="Remove Picture" accessibilityLabel="Remove profile picture" variant="outline" size="small" fullWidth={false} disabled={avatarPending} onPress={() => { void removeAvatar(); }} /> : null}
          </View>
          <View style={{ marginTop: avatarFeedback ? spacing.md : 0, width: "100%" }}><InlineFeedback type={avatarFeedback?.type} message={avatarFeedback?.message} /></View>
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
          <Text style={[styles.support, { color: theme.colors.textSecondary, marginTop: spacing.lg }]}>Use Settings to update profile details, password, verified email and preferences.</Text>
        </View>
        {!user.is_email_verified ? <AppButton title="Verify Email" onPress={onVerify} style={{ marginTop: spacing.lg }} /> : null}
        {onSettings ? <AppButton title="Open Settings" onPress={onSettings} style={{ marginTop: spacing.md }} /> : null}
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
  avatarImage: { width: "100%", height: "100%", borderRadius: 34 },
  avatarActions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  avatarText: { fontSize: 23, fontWeight: "800" },
  name: { fontWeight: "800" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "800" },
  row: { borderTopWidth: 1 },
  support: { fontSize: 12, lineHeight: 18 },
});
