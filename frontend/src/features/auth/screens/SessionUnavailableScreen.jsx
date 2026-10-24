import { StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuth } from "../context/AuthProvider";

export function SessionUnavailableScreen() {
  const { theme, spacing, layout } = useAppTheme();
  const { sessionIssue, retryVerification, logout } = useAuth();
  const removalFailed = sessionIssue?.kind === "storage-remove";
  const primaryAction = removalFailed ? logout : retryVerification;

  const runSafely = (action) => {
    void action().catch(() => {});
  };

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <View style={[styles.shell, { padding: spacing.xl, maxWidth: layout.formMaxWidth }]}>
        <FeedbackState
          type="error"
          title={removalFailed ? "Sign out needs attention" : "Session verification unavailable"}
          message={sessionIssue?.message || "ICMS could not verify the saved session safely."}
          actionLabel={removalFailed ? "Retry Sign Out" : "Try Again"}
          onAction={() => runSafely(primaryAction)}
        />
        {!removalFailed ? (
          <AppButton
            title="Sign Out on This Device"
            variant="outline"
            onPress={() => runSafely(logout)}
            style={{ marginTop: spacing.md }}
          />
        ) : null}
        <Text style={[styles.note, { color: theme.colors.textSecondary, marginTop: spacing.md }]}>
          ICMS does not expose protected information until the server confirms this session.
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  shell: { width: "100%", flex: 1, alignSelf: "center", justifyContent: "center" },
  note: { fontSize: 12, lineHeight: 18, textAlign: "center" },
});
