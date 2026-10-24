import { StyleSheet, Text, View } from "react-native";

import { BrandMark } from "../../../components/brand/BrandMark";
import { AppButton } from "../../../components/ui/AppButton";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuth } from "../context/AuthProvider";

export function SessionScreen({ onProfile }) {
  const { theme, spacing, radius, layout, typography } = useAppTheme();
  const { user, logout } = useAuth();

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <View style={[styles.shell, { padding: spacing.xl, maxWidth: layout.formMaxWidth }]}>
        <BrandMark size={58} showWordmark />
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: spacing.xl, marginTop: spacing.xl }]}>
          <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: "800" }}>
            Session confirmed
          </Text>
          <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>
            This temporary protected screen confirms that ICMS verified your account with the server.
          </Text>
          <Text style={[styles.name, { color: theme.colors.text, marginTop: spacing.xl }]}>{user?.full_name}</Text>
          <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.xs }}>{user?.email}</Text>
          <AppButton title="View Profile" onPress={onProfile} style={{ marginTop: spacing.xl }} />
          <AppButton
            title="Log Out"
            variant="outline"
            onPress={() => { void logout().catch(() => {}); }}
            style={{ marginTop: spacing.md }}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  shell: { width: "100%", flex: 1, alignSelf: "center", justifyContent: "center" },
  card: { borderWidth: 1 },
  name: { fontSize: 18, fontWeight: "700" },
});
