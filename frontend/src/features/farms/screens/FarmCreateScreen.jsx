import { Keyboard, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRef, useState } from "react";

import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuthSubmission } from "../../auth/hooks/useAuthSubmission";
import { useFarm } from "../context/FarmProvider";
import { farmErrorMessage } from "../farmErrors";
import { FARM_FIELD_LIMITS, farmPayload, validateFarm } from "../farmValidation";

export function FarmCreateScreen({ onCreated, onBack, createFarm }) {
  const farm = useFarm();
  const { theme, spacing, typography, layout } = useAppTheme();
  const locationRef = useRef(null);
  const descriptionRef = useRef(null);
  const [values, setValues] = useState({ name: "", location: "", description: "" });
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const { submitting, run } = useAuthSubmission();
  const create = createFarm || farm.createFarm;

  const update = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFeedback(null);
  };

  const submit = async () => {
    if (submitting) return;
    Keyboard.dismiss();
    const nextErrors = validateFarm(values);
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      setFeedback("Review the highlighted farm information and try again.");
      return;
    }
    setErrors({});
    setFeedback(null);
    const result = await run(() => create(farmPayload(values)));
    if (result.cancelled || result.skipped) return;
    if (result.error) {
      setErrors(result.error?.fieldErrors || {});
      setFeedback(farmErrorMessage(result.error));
      return;
    }
    if (!result.value?.created) {
      setErrors(result.value?.error?.fieldErrors || {});
      setFeedback(farmErrorMessage(result.value?.error, { ambiguous: result.value?.ambiguous }));
      return;
    }
    if (!result.value.selected) {
      setFeedback("Your farm was created, but its access could not be confirmed yet. Refresh your farms before trying to create another.");
      return;
    }
    onCreated?.(result.value.farm);
  };

  return (
    <Screen style={{ backgroundColor: theme.colors.background }}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content, { maxWidth: layout.formMaxWidth, padding: spacing.xl }]}>
        <Text style={{ color: theme.colors.primary, fontSize: typography.sizes.caption, fontWeight: typography.weights.extrabold, letterSpacing: typography.letterSpacing.eyebrow }}>FARM ONBOARDING</Text>
        <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold, marginTop: spacing.xs }}>Create your farm workspace</Text>
        <Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>ICMS will ask the server to create the farm and its authoritative owner membership in one transaction.</Text>
        <AppCard style={{ marginTop: spacing.xl }}>
          <View style={{ gap: spacing.lg }}>
            {feedback ? <InlineFeedback type="error" message={feedback} /> : null}
            <AppInput
              label="Farm Name"
              placeholder="e.g. Green Valley Dairy"
              value={values.name}
              onChangeText={(value) => update("name", value)}
              error={errors.name}
              required
              maxLength={FARM_FIELD_LIMITS.name}
              autoCapitalize="words"
              autoComplete="organization"
              returnKeyType="next"
              onSubmitEditing={() => locationRef.current?.focus()}
              testID="farm-name"
            />
            <AppInput
              inputRef={locationRef}
              label="Location"
              placeholder="City or region (optional)"
              value={values.location}
              onChangeText={(value) => update("location", value)}
              error={errors.location}
              helperText="Optional. Keep location details appropriate for your team."
              maxLength={FARM_FIELD_LIMITS.location}
              autoCapitalize="words"
              returnKeyType="next"
              onSubmitEditing={() => descriptionRef.current?.focus()}
              testID="farm-location"
            />
            <AppInput
              inputRef={descriptionRef}
              label="Description"
              placeholder="A short description of this farm (optional)"
              value={values.description}
              onChangeText={(value) => update("description", value)}
              error={errors.description}
              maxLength={FARM_FIELD_LIMITS.description}
              multiline
              autoCapitalize="sentences"
              testID="farm-description"
            />
            <AppButton title="Create Farm" onPress={submit} loading={submitting || farm.status === "creating"} disabled={submitting || farm.status === "creating"} accessibilityHint="Creates the farm through the secured ICMS server" testID="farm-create-submit" />
            <AppButton title="Cancel" variant="outline" onPress={onBack} disabled={submitting || farm.status === "creating"} />
          </View>
        </AppCard>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({ content: { width: "100%", alignSelf: "center", paddingBottom: 48 } });
