import { Keyboard, View } from "react-native";
import { useRef, useState } from "react";

import { authApi } from "../../../api/auth";
import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { authErrorMessage, authFieldErrors } from "../authErrors";
import { requireRegistrationResponse } from "../authContracts";
import { AuthLayout } from "../components/AuthLayout";
import { AuthSuccessState } from "../components/AuthSuccessState";
import { AuthSwitchPrompt } from "../components/AuthSwitchPrompt";
import { useAuthSubmission } from "../hooks/useAuthSubmission";
import { signupPayload, validateSignup } from "../validation/authValidation";

export function SignupScreen({ onBack, onLogIn, api = authApi }) {
  const { spacing } = useAppTheme();
  const emailRef = useRef(null);
  const passwordRef = useRef(null);
  const confirmationRef = useRef(null);
  const [values, setValues] = useState({ fullName: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const [registeredUser, setRegisteredUser] = useState(null);
  const [resendFeedback, setResendFeedback] = useState(null);
  const submission = useAuthSubmission();
  const resend = useAuthSubmission();

  const update = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFeedback(null);
  };

  const submit = async () => {
    if (submission.submitting) return;
    Keyboard.dismiss();
    const nextErrors = validateSignup(values);
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      setFeedback("Review the highlighted information and try again.");
      return;
    }

    setErrors({});
    setFeedback(null);
    const result = await submission.run(async (signal) => {
      const response = await api.register(signupPayload(values), { signal });
      return requireRegistrationResponse(response);
    });
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setErrors(authFieldErrors(result.error));
      setFeedback(authErrorMessage(result.error, "signup"));
      return;
    }

    setRegisteredUser(result.value);
    setValues((current) => ({ ...current, password: "", confirmPassword: "" }));
  };

  const resendVerification = async () => {
    if (!registeredUser || resend.submitting) return;
    setResendFeedback(null);
    const result = await resend.run((signal) => api.resendVerification(registeredUser.email, { signal }));
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setResendFeedback({ type: "error", message: authErrorMessage(result.error, "signup") });
      return;
    }
    setResendFeedback({ type: "success", message: "If verification is still required, a new email will be sent." });
  };

  return (
    <AuthLayout eyebrow="CREATE YOUR ACCOUNT" title="Start with ICMS" subtitle="Create your personal account. Farm setup follows in a later guided step." onBack={onBack}>
      {registeredUser ? (
        <AuthSuccessState
          title="Account created"
          message={registeredUser.is_email_verified ? "Your account is ready." : `Check ${registeredUser.email} for your verification email.`}
          detail="Registration does not sign you in or create a farm. Continue to login after verifying your email."
          primaryTitle="Go to Log In"
          onPrimary={onLogIn}
          secondaryTitle={registeredUser.is_email_verified ? undefined : "Resend Verification Email"}
          onSecondary={resendVerification}
          secondaryLoading={resend.submitting}
          feedback={resendFeedback}
        />
      ) : (
        <View style={{ gap: spacing.lg }}>
          {feedback ? <InlineFeedback type="error" message={feedback} /> : null}
          <AppInput
            label="Full Name"
            placeholder="Your full name"
            value={values.fullName}
            onChangeText={(value) => update("fullName", value)}
            error={errors.fullName}
            required
            autoCapitalize="words"
            autoComplete="name"
            textContentType="name"
            maxLength={150}
            returnKeyType="next"
            onSubmitEditing={() => emailRef.current?.focus()}
            blurOnSubmit={false}
            testID="signup-full-name"
          />
          <AppInput
            inputRef={emailRef}
            label="Email Address"
            placeholder="you@example.com"
            value={values.email}
            onChangeText={(value) => update("email", value)}
            error={errors.email}
            required
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="email"
            textContentType="emailAddress"
            maxLength={254}
            returnKeyType="next"
            onSubmitEditing={() => passwordRef.current?.focus()}
            blurOnSubmit={false}
            testID="signup-email"
          />
          <AppInput
            inputRef={passwordRef}
            label="Password"
            placeholder="Create a password"
            value={values.password}
            onChangeText={(value) => update("password", value)}
            error={errors.password}
            helperText="Use 8–128 characters."
            required
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
            maxLength={128}
            returnKeyType="next"
            onSubmitEditing={() => confirmationRef.current?.focus()}
            blurOnSubmit={false}
            testID="signup-password"
          />
          <AppInput
            inputRef={confirmationRef}
            label="Confirm Password"
            placeholder="Enter your password again"
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
            testID="signup-confirm-password"
          />
          <AppButton
            title="Create Account"
            onPress={submit}
            loading={submission.submitting}
            disabled={submission.submitting}
            accessibilityHint="Creates your ICMS account"
            testID="signup-submit"
          />
          <AuthSwitchPrompt message="Already have an account?" action="Log In" onPress={onLogIn} />
        </View>
      )}
    </AuthLayout>
  );
}
