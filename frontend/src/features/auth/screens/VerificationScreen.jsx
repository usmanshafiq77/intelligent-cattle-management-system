import { useEffect, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { authApi } from "../../../api/auth";
import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { requireMessageResponse } from "../authContracts";
import { useOptionalAuth } from "../context/AuthProvider";
import { useAuthSubmission } from "../hooks/useAuthSubmission";
import { verificationErrorMessage } from "../verificationErrors";
import { isVerificationEmail, normalizeVerificationEmail, requestVerificationResend } from "../verificationService";

export function VerificationScreen({ initialToken = "", onBack, api = authApi }) {
  const { theme, spacing, radius, shadows, typography, layout } = useAppTheme();
  const auth = useOptionalAuth();
  const [token, setToken] = useState(initialToken);
  const [email, setEmail] = useState(auth?.user?.email || "");
  const [feedback, setFeedback] = useState(null);
  const [cooldown, setCooldown] = useState(0);
  const verify = useAuthSubmission();
  const resend = useAuthSubmission();
  const autoVerificationAttempted = useRef(false);

  useEffect(() => {
    if (!cooldown) return undefined;
    const timer = setInterval(() => setCooldown((current) => Math.max(0, current - 1)), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const submitVerification = async (candidate = token) => {
    const trimmed = candidate.trim();
    if (!trimmed) {
      setFeedback({ type: "error", message: "Enter the verification code from your email." });
      return;
    }
    setFeedback(null);
    const result = await verify.run(async (signal) => requireMessageResponse(await api.verifyEmail(trimmed, { signal })));
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setFeedback({ type: "error", message: verificationErrorMessage(result.error) });
      return;
    }
    setToken("");
    if (auth?.refreshProfile) await auth.refreshProfile().catch(() => {});
    setFeedback({ type: "success", message: "Email verified successfully. Your profile has been refreshed." });
  };

  useEffect(() => {
    if (!initialToken || autoVerificationAttempted.current) return;
    autoVerificationAttempted.current = true;
    void submitVerification(initialToken);
  }, [initialToken]);

  const submitResend = async () => {
    const normalizedEmail = normalizeVerificationEmail(email);
    if (!isVerificationEmail(normalizedEmail)) {
      setFeedback({ type: "error", message: "Enter a valid email address to request verification." });
      return;
    }
    setFeedback(null);
    const result = await resend.run((signal) => requestVerificationResend(api, normalizedEmail, signal));
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      if (result.error.status === 429 && result.error.retryAfterSeconds) setCooldown(result.error.retryAfterSeconds);
      setFeedback({ type: "error", message: verificationErrorMessage(result.error, "resend") });
      return;
    }
    setFeedback({ type: "success", message: "If this account exists and still needs verification, an email will be sent." });
  };

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.container, { padding: spacing.xl, maxWidth: layout.formMaxWidth }]}>
        <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: "800" }}>Verify your email</Text>
        <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>Enter the one-time verification code from your ICMS email. Codes are never saved on this device.</Text>
        <View style={[styles.card, shadows.large, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: radius.xl, padding: spacing.xl, marginTop: spacing.xl }]}>
          {feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}
          <AppInput label="Verification Code" placeholder="Paste the code from your email" value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false} maxLength={512} multiline testID="verification-token" style={{ marginTop: feedback ? spacing.lg : 0 }} />
          <AppButton title="Verify Email" loading={verify.submitting} disabled={verify.submitting} onPress={() => submitVerification()} style={{ marginTop: spacing.lg }} testID="verify-email-submit" />
          <View style={[styles.separator, { backgroundColor: theme.colors.border, marginVertical: spacing.xl }]} />
          <Text style={{ color: theme.colors.text, fontWeight: "700" }}>Need another email?</Text>
          <Text style={{ color: theme.colors.textSecondary, fontSize: 13, marginTop: spacing.xs }}>For privacy, ICMS returns the same response whether or not an account exists.</Text>
          <AppInput label="Email Address" placeholder="you@example.com" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" testID="verification-resend-email" style={{ marginTop: spacing.lg }} />
          <AppButton title={cooldown ? `Try Again in ${cooldown}s` : "Resend Verification Email"} variant="outline" loading={resend.submitting} disabled={resend.submitting || cooldown > 0} onPress={submitResend} style={{ marginTop: spacing.md }} testID="resend-verification-submit" />
          <AppButton title="Back" variant="outline" onPress={onBack} style={{ marginTop: spacing.md }} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { width: "100%", alignSelf: "center", flexGrow: 1, justifyContent: "center" },
  card: { borderWidth: 1 },
  separator: { height: 1 },
});
