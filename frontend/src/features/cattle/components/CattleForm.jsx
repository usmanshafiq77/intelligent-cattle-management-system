import { Pressable, StyleSheet, Text, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ACQUISITION_METHODS, categoriesForSex, SEXES, SPECIES } from "../cattleOptions";
import { OptionField } from "./OptionField";

export function CattleForm({ values, errors = {}, breeds = [], onChange, onSubmit, onCancel, pending, editing = false, feedback }) {
  const { theme, radius, spacing, typography } = useAppTheme();
  const set = (field) => (value) => onChange(field, value);
  const availableBreeds = breeds.filter((breed) => breed.species === values.species);

  return (
    <View style={{ gap: spacing.xl }}>
      {feedback ? <InlineFeedback type="error" message={feedback} /> : null}
      <AppInput testID="cattle-tag" label="Tag number" required value={values.tag_number} onChangeText={set("tag_number")} error={errors.tag_number} maxLength={100} disabled={pending} />
      <AppInput testID="cattle-name" label="Animal name" value={values.name} onChangeText={set("name")} error={errors.name} maxLength={150} disabled={pending} />
      <OptionField testID="cattle-species" label="Species" required value={values.species} options={SPECIES} onChange={set("species")} error={errors.species} disabled={pending || editing} />
      <OptionField testID="cattle-sex" label="Sex" required value={values.sex} options={SEXES} onChange={(sex) => {
        const categories = categoriesForSex(sex);
        onChange("sex", sex);
        if (!categories.includes(values.category)) onChange("category", categories[0]);
      }} error={errors.sex} disabled={pending || editing} />
      <OptionField testID="cattle-category" label="Category" required value={values.category} options={categoriesForSex(values.sex)} onChange={set("category")} error={errors.category} disabled={pending} />

      <View style={{ gap: spacing.sm }}>
        <Text style={{ color: theme.colors.text, fontSize: typography.sizes.small, fontWeight: typography.weights.semibold }}>Breed</Text>
        <View accessibilityRole="radiogroup" accessibilityLabel="Breed" style={styles.options}>
          <Pressable testID="cattle-breed-none" accessibilityRole="radio" accessibilityState={{ checked: !values.breed_id }} onPress={() => set("breed_id")("")} disabled={pending} style={({ pressed }) => [styles.option, { borderColor: !values.breed_id ? theme.colors.primary : theme.colors.border, backgroundColor: !values.breed_id ? theme.colors.surfaceSecondary : theme.colors.surface, borderRadius: radius.md, opacity: pressed ? 0.72 : 1 }]}>
            <Text style={{ color: theme.colors.text }}>Not specified</Text>
          </Pressable>
          {availableBreeds.map((breed) => <Pressable key={breed.id} testID={`cattle-breed-${breed.id}`} accessibilityRole="radio" accessibilityState={{ checked: values.breed_id === breed.id }} onPress={() => set("breed_id")(breed.id)} disabled={pending} style={({ pressed }) => [styles.option, { borderColor: values.breed_id === breed.id ? theme.colors.primary : theme.colors.border, backgroundColor: values.breed_id === breed.id ? theme.colors.surfaceSecondary : theme.colors.surface, borderRadius: radius.md, opacity: pressed ? 0.72 : 1 }]}><Text style={{ color: theme.colors.text }}>{breed.name}</Text></Pressable>)}
        </View>
      </View>

      <View style={styles.twoColumns}>
        <AppInput testID="cattle-dob" label="Date of birth" placeholder="YYYY-MM-DD" value={values.date_of_birth} onChangeText={set("date_of_birth")} error={errors.date_of_birth} maxLength={10} disabled={pending} style={styles.field} />
        <AppInput testID="cattle-acquisition-date" label="Acquisition date" placeholder="YYYY-MM-DD" value={values.acquisition_date} onChangeText={set("acquisition_date")} error={errors.acquisition_date} maxLength={10} disabled={pending} style={styles.field} />
      </View>
      <Pressable testID="cattle-estimated-dob" accessibilityRole="checkbox" accessibilityState={{ checked: values.birth_date_estimated, disabled: pending }} disabled={pending} onPress={() => set("birth_date_estimated")(!values.birth_date_estimated)} style={styles.checkbox}>
        <View style={[styles.checkBox, { borderColor: theme.colors.primary, backgroundColor: values.birth_date_estimated ? theme.colors.primary : theme.colors.surface }]}><Text style={{ color: theme.colors.onPrimary }}>{values.birth_date_estimated ? "✓" : ""}</Text></View>
        <Text style={{ color: theme.colors.text }}>Birth date is estimated</Text>
      </Pressable>
      <OptionField testID="cattle-acquisition-method" label="Acquisition method" value={values.acquisition_method} options={ACQUISITION_METHODS} onChange={set("acquisition_method")} disabled={pending} />
      <AppInput testID="cattle-acquisition-source" label="Acquisition source" value={values.acquisition_source} onChangeText={set("acquisition_source")} maxLength={255} disabled={pending} />
      <View style={styles.twoColumns}>
        <AppInput testID="cattle-cost" label="Acquisition cost" keyboardType="decimal-pad" value={values.initial_acquisition_cost} onChangeText={set("initial_acquisition_cost")} error={errors.initial_acquisition_cost} disabled={pending} style={styles.field} />
        <AppInput testID="cattle-currency" label="Currency" placeholder="PKR" autoCapitalize="characters" value={values.initial_acquisition_currency} onChangeText={set("initial_acquisition_currency")} error={errors.initial_acquisition_currency} maxLength={3} disabled={pending} style={styles.field} />
      </View>
      <View style={styles.twoColumns}>
        <AppInput testID="cattle-color" label="Color" value={values.color} onChangeText={set("color")} maxLength={100} disabled={pending} style={styles.field} />
        {!editing ? <AppInput testID="cattle-weight" label="Initial weight (kg)" keyboardType="decimal-pad" value={values.initial_weight_kg} onChangeText={set("initial_weight_kg")} error={errors.initial_weight_kg} disabled={pending} style={styles.field} /> : null}
      </View>
      {!editing ? <AppInput testID="cattle-weight-method" label="Weight method" value={values.initial_weight_method} onChangeText={set("initial_weight_method")} maxLength={50} disabled={pending} /> : null}
      <AppInput testID="cattle-marks" label="Identification marks" value={values.identification_marks} onChangeText={set("identification_marks")} maxLength={500} multiline disabled={pending} />
      <AppInput testID="cattle-notes" label="Notes" value={values.notes} onChangeText={set("notes")} maxLength={5000} multiline disabled={pending} />
      <View style={styles.actions}>
        <AppButton testID="cattle-submit" title={editing ? "Save changes" : "Register cattle"} onPress={onSubmit} loading={pending} disabled={pending} fullWidth={false} />
        <AppButton title="Cancel" variant="outline" onPress={onCancel} disabled={pending} fullWidth={false} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  options: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  option: { minHeight: 44, justifyContent: "center", paddingHorizontal: 12, borderWidth: 1 },
  twoColumns: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  field: { minWidth: 220, flex: 1 },
  checkbox: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: 10 },
  checkBox: { width: 24, height: 24, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
});
