import { Keyboard, View } from "react-native";
import { useState } from "react";

import { authApi } from "../../../api/auth";
import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { requireMessageResponse } from "../authContracts";
import { AuthLayout } from "../components/AuthLayout";
import { AuthSuccessState } from "../components/AuthSuccessState";
import { useAuthSubmission } from "../hooks/useAuthSubmission";
import { normalizeEmail, validateForgotPassword } from "../validation/authValidation";

function requestErrorMessage(error) {
  if (error?.status === 429) {
    const wait = error.retryAfterSeconds ? ` Try again in ${error.retryAfterSeconds} seconds.` : " Please wait before trying again.";
    return `Too many reset requests.${wait}`;
  }
  if (error?.code === "NETWORK_ERROR") return "ICMS cannot reach the server. Check your connection and try again.";
  if (error?.code === "TIMEOUT") return "The request timed out. Please try again.";
  return "Password reset instructions could not be requested. Please try again.";
}

export function ForgotPasswordScreen({ onBack, onLogIn, api = authApi }) {
  const { spacing } = useAppTheme();
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [complete, setComplete] = useState(false);
  const { submitting, run } = useAuthSubmission();

  const submit = async () => {
    if (submitting) return;
    Keyboard.dismiss();
    const errors = validateForgotPassword({ email });
    if (errors.email) {
      setError(errors.email);
      setFeedback("Enter a valid email address and try again.");
      return;
    }
    setError(null);
    setFeedback(null);
    const normalized = normalizeEmail(email);
    const result = await run(async (signal) => requireMessageResponse(await api.forgotPassword(normalized, { signal })));
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setFeedback(requestErrorMessage(result.error));
      return;
    }
    setEmail("");
    setComplete(true);
  };

  return (
    <AuthLayout eyebrow="ACCOUNT RECOVERY" title="Forgot Password" subtitle="Request a secure, one-time password reset link." onBack={onBack}>
      {complete ? (
        <AuthSuccessState
          title="Check your email"
          message="If the account is eligible, password reset instructions will be sent."
          detail="For your privacy, ICMS shows the same confirmation for every email address."
          primaryTitle="Back to Log In"
          onPrimary={onLogIn}
        />
      ) : (
        <View style={{ gap: spacing.lg }}>
          {feedback ? <InlineFeedback type="error" message={feedback} /> : null}
          <AppInput
            label="Email Address"
            placeholder="you@example.com"
            value={email}
            onChangeText={(value) => { setEmail(value); setError(null); setFeedback(null); }}
            error={error}
            required
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="email"
            textContentType="emailAddress"
            returnKeyType="done"
            onSubmitEditing={submit}
            testID="forgot-password-email"
          />
          <AppButton title="Send Reset Instructions" onPress={submit} loading={submitting} disabled={submitting} testID="forgot-password-submit" />
          <AppButton title="Back to Log In" variant="outline" onPress={onLogIn} />
        </View>
      )}
    </AuthLayout>
  );
}
