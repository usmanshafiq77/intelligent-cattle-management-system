import { Keyboard, View } from "react-native";
import { useRef, useState } from "react";

import { authApi } from "../../../api/auth";
import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { authErrorMessage, authFieldErrors } from "../authErrors";
import { requireLoginResponse } from "../authContracts";
import { useOptionalAuth } from "../context/AuthProvider";
import { AuthLayout } from "../components/AuthLayout";
import { AuthSuccessState } from "../components/AuthSuccessState";
import { AuthSwitchPrompt } from "../components/AuthSwitchPrompt";
import { useAuthSubmission } from "../hooks/useAuthSubmission";
import { loginPayload, validateLogin } from "../validation/authValidation";

export function LoginScreen({ onBack, onCreateAccount, api = authApi, tokenSetter, completeLogin }) {
  const { spacing } = useAppTheme();
  const passwordRef = useRef(null);
  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const [signedIn, setSignedIn] = useState(false);
  const { submitting, run } = useAuthSubmission();
  const auth = useOptionalAuth();
  const completeSession = completeLogin || auth?.completeLogin;

  const update = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFeedback(null);
  };

  const submit = async () => {
    if (submitting) return;
    Keyboard.dismiss();
    const nextErrors = validateLogin(values);
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      setFeedback("Review the highlighted information and try again.");
      return;
    }

    setErrors({});
    setFeedback(null);
    const result = await run(async (signal) => {
      const response = await api.login(loginPayload(values), { signal });
      if (completeSession) return completeSession(response);
      const contract = requireLoginResponse(response);
      if (typeof tokenSetter !== "function") throw new Error("Authentication session handling is unavailable.");
      await tokenSetter(contract.accessToken);
      return contract;
    });
    if (result.skipped || result.cancelled) return;
    if (result.error) {
      setErrors(authFieldErrors(result.error));
      setFeedback(authErrorMessage(result.error, "login"));
      return;
    }

    setValues((current) => ({ ...current, password: "" }));
    setSignedIn(true);
  };

  return (
    <AuthLayout eyebrow="SECURE ACCESS" title="Welcome Back" subtitle="Sign in to continue managing your ICMS workspace." onBack={onBack}>
      {signedIn ? (
        <AuthSuccessState
          title="Login successful"
          message="Your session credentials have been accepted securely."
          detail="Session restoration and authenticated destination routing are introduced in later Step 19.6 work."
          primaryTitle="Return to Welcome"
          onPrimary={onBack}
        />
      ) : (
        <View style={{ gap: spacing.lg }}>
          {feedback ? <InlineFeedback type="error" message={feedback} /> : null}
          <AppInput
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
            returnKeyType="next"
            onSubmitEditing={() => passwordRef.current?.focus()}
            blurOnSubmit={false}
            testID="login-email"
          />
          <AppInput
            inputRef={passwordRef}
            label="Password"
            placeholder="Enter your password"
            value={values.password}
            onChangeText={(value) => update("password", value)}
            error={errors.password}
            required
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="current-password"
            textContentType="password"
            maxLength={128}
            returnKeyType="done"
            onSubmitEditing={submit}
            testID="login-password"
          />
          <AppButton
            title="Log In"
            onPress={submit}
            loading={submitting}
            disabled={submitting}
            accessibilityHint="Submits your credentials securely to ICMS"
            testID="login-submit"
          />
          <AuthSwitchPrompt message="New to ICMS?" action="Create Account" onPress={onCreateAccount} />
        </View>
      )}
    </AuthLayout>
  );
}
