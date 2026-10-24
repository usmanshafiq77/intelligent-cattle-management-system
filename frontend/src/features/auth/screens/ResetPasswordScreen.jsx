import { Keyboard, View } from "react-native";
import { useRef, useState } from "react";

import { authApi } from "../../../api/auth";
import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { requireMessageResponse } from "../authContracts";
import { AuthLayout } from "../components/AuthLayout";
import { AuthSuccessState } from "../components/AuthSuccessState";
import { useAuthSubmission } from "../hooks/useAuthSubmission";
import { validateResetPassword } from "../validation/authValidation";

function resetErrorMessage(error) {
  if (error?.status === 400) return "This password reset link is invalid, expired, revoked, or has already been used.";
  if (error?.status === 429) return "Too many reset attempts. Please wait before trying again.";
  if (error?.code === "NETWORK_ERROR") return "ICMS cannot reach the server. Check your connection and try again.";
  if (error?.code === "TIMEOUT") return "The request timed out. Please try again.";
  return "Your password could not be reset. Please request a new link and try again.";
}

export function ResetPasswordScreen({ token, onBack, onLogIn, onRequestNewLink, api = authApi }) {
  const { spacing } = useAppTheme();
  const confirmRef = useRef(null);
  const [values, setValues] = useState({ password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const [complete, setComplete] = useState(false);
  const { submitting, run } = useAuthSubmission();
  const usableToken = typeof token === "string" ? token.trim() : "";

  const update = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFeedback(null);
  };

  const submit = async () => {
    if (submitting) return;
    if (!usableToken) {
      setFeedback("This password reset link is missing its secure token. Request a new link.");
      return;
    }
    Keyboard.dismiss();
    const nextErrors = validateResetPassword(values);
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      setFeedback("Review the highlighted information and try again.");
      return;
    }
    setErrors({});
    setFeedback(null);
    const result = await run(async (signal) => requireMessageResponse(await api.resetPassword(usableToken, values.password, { signal })));
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setFeedback(resetErrorMessage(result.error));
      return;
    }
    setValues({ password: "", confirmPassword: "" });
    setComplete(true);
  };

  return (
    <AuthLayout eyebrow="ACCOUNT RECOVERY" title="Reset Password" subtitle="Choose a new password for your ICMS account." onBack={onBack}>
      {complete ? (
        <AuthSuccessState title="Password reset" message="Your password was changed successfully. Sign in with your new password." primaryTitle="Go to Log In" onPrimary={onLogIn} />
      ) : (
        <View style={{ gap: spacing.lg }}>
          {feedback || !usableToken ? (
            <InlineFeedback type="error" message={feedback || "This password reset link is missing its secure token. Request a new link."} />
          ) : null}
          <AppInput
            label="New Password"
            placeholder="At least 8 characters"
            value={values.password}
            onChangeText={(value) => update("password", value)}
            error={errors.password}
            required
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
            maxLength={128}
            returnKeyType="next"
            onSubmitEditing={() => confirmRef.current?.focus()}
            blurOnSubmit={false}
            testID="reset-password-new"
          />
          <AppInput
            inputRef={confirmRef}
            label="Confirm New Password"
            placeholder="Re-enter your password"
            value={values.confirmPassword}
            onChangeText={(value) => update("confirmPassword", value)}
            error={errors.confirmPassword}
            required
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
            maxLength={128}
            returnKeyType="done"
            onSubmitEditing={submit}
            testID="reset-password-confirm"
          />
          <AppButton title="Reset Password" onPress={submit} loading={submitting} disabled={submitting || !usableToken} testID="reset-password-submit" />
          {!usableToken ? <AppButton title="Request a New Link" variant="outline" onPress={onRequestNewLink} /> : null}
        </View>
      )}
    </AuthLayout>
  );
}
