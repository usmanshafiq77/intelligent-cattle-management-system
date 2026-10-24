import { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { invitationsApi } from "../../../api/invitations";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useOptionalAuth } from "../../auth/context/AuthProvider";
import { useAuthSubmission } from "../../auth/hooks/useAuthSubmission";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm } from "../../permissions/guards";
import { assignableInvitationRoles, requireInvitationResponse } from "../staffContracts";
import { staffErrorMessage } from "../staffErrors";

const emailOk = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

export function InviteStaffScreen({ onBack, api = invitationsApi }) {
  const farm = useFarm();
  const auth = useOptionalAuth();
  const { theme, spacing, typography, layout } = useAppTheme();
  const { submitting, run } = useAuthSubmission();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("WORKER");
  const [feedback, setFeedback] = useState(null);
  const authoritativeOwner = farm.membership?.role === "FARM_OWNER"
    && (!auth || farm.activeFarm?.owner_id === auth.user?.id);

  const submit = async () => {
    if (!authoritativeOwner || !farm.activeFarm?.id) return;
    if (!emailOk(email)) {
      setFeedback({ type: "error", message: "Enter a valid invitee email address." });
      return;
    }
    setFeedback(null);
    const result = await run(() => api.create(farm.activeFarm.id, {
      email: email.trim().toLowerCase(),
      role,
    }));
    if (result.error) {
      setFeedback({
        type: "error",
        message: staffErrorMessage(result.error, { invitation: true }),
      });
      return;
    }
    try {
      const invitation = requireInvitationResponse(result.value, farm.activeFarm.id);
      setEmail("");
      setFeedback({
        type: invitation.delivery_status === "FAILED" ? "warning" : "success",
        message: invitation.delivery_status === "FAILED"
          ? "Invitation created, but email delivery failed. Reissue it after the email service is available."
          : "Invitation created and handed to the configured email service.",
      });
    } catch {
      setFeedback({
        type: "error",
        message: "The invitation response could not be verified. Refresh invitations before retrying.",
      });
    }
  };

  return (
    <RequireFarm>
      <Screen style={{ backgroundColor: theme.colors.background }}>
        {!authoritativeOwner ? (
          <FeedbackState type="error" title="Access denied" message="Only the verified farm owner can invite staff." />
        ) : (
          <ScrollView contentContainerStyle={{ width: "100%", alignSelf: "center", maxWidth: layout.formMaxWidth, padding: spacing.xl }}>
            <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>Invite staff</Text>
            <AppCard style={{ marginTop: spacing.xl }}>
              <View style={{ gap: spacing.lg }}>
                {feedback ? <InlineFeedback type={feedback.type} message={feedback.message} /> : null}
                <AppInput label="Email address" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" testID="invite-email" required />
                <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>Farm role</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
                  {assignableInvitationRoles.map((item) => <AppButton key={item} title={item.replace("_", " ")} variant={role === item ? "primary" : "outline"} size="small" fullWidth={false} onPress={() => setRole(item)} />)}
                </View>
                <AppButton title="Send invitation" onPress={submit} loading={submitting} disabled={submitting} testID="invite-submit" />
                <AppButton title="Back to staff" variant="outline" onPress={onBack} />
              </View>
            </AppCard>
          </ScrollView>
        )}
      </Screen>
    </RequireFarm>
  );
}
