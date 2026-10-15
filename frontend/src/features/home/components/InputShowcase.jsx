import { useState } from "react";
import { View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ShowcaseSection } from "./ShowcaseSection";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InputShowcase() {
  const { spacing } = useAppTheme();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notes, setNotes] = useState("");
  const [showValidation, setShowValidation] = useState(false);
  const [message, setMessage] = useState("");
  const nameError = showValidation && !name.trim() ? "Name is required." : "";
  const emailError = showValidation
    ? !email.trim()
      ? "Email is required."
      : !EMAIL_PATTERN.test(email.trim())
        ? "Enter a valid email address."
        : ""
    : "";
  const passwordError = showValidation && password.length < 8 ? "Use at least 8 characters." : "";

  const update = (setter) => (value) => {
    setter(value);
    setMessage("");
  };

  const validate = () => {
    setShowValidation(true);
    const valid = name.trim() && EMAIL_PATTERN.test(email.trim()) && password.length >= 8;
    setMessage(valid ? "Sample form is valid. No data was sent or saved." : "Correct the highlighted sample fields.");
  };

  return (
    <ShowcaseSection
      title="Inputs and validation"
      description="The fields demonstrate keyboard behavior, password visibility, helper text, errors, multiline content, and disabled states."
      entranceDelay={150}
    >
      <View style={{ gap: spacing.lg }}>
        <AppInput testID="name-input" label="Full name" placeholder="Enter your full name" value={name} onChangeText={update(setName)} autoCapitalize="words" autoComplete="name" required error={nameError} />
        <AppInput testID="email-input" label="Email address" placeholder="name@example.com" value={email} onChangeText={update(setEmail)} keyboardType="email-address" autoCapitalize="none" autoComplete="email" required error={emailError} />
        <AppInput testID="password-input" label="Password" placeholder="At least 8 characters" value={password} onChangeText={update(setPassword)} secureTextEntry autoCapitalize="none" autoComplete="off" required helperText="Visual preview only; the password is never submitted." error={passwordError} />
        <AppInput label="Farm notes" placeholder="Optional multiline notes" value={notes} onChangeText={update(setNotes)} multiline maxLength={240} helperText={`${notes.length}/240 characters`} />
        <AppInput label="Disabled input" value="Read-only preview" disabled />
        <AppButton title="Validate sample form" onPress={validate} />
      </View>
      <InlineFeedback type={message.startsWith("Sample") ? "success" : "error"} message={message} />
    </ShowcaseSection>
  );
}
