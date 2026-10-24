import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { invitationsApi } from "../../../api/invitations";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { AppInput } from "../../../components/ui/AppInput";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { Screen } from "../../../components/ui/Screen";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuthSubmission } from "../../auth/hooks/useAuthSubmission";
import { useFarm } from "../../farms/context/FarmProvider";
import { staffErrorMessage } from "../staffErrors";
import { requireInvitationAcceptance } from "../staffContracts";

export function AcceptInvitationScreen({ initialToken = "", onAccepted, api = invitationsApi }) {
  const farm = useFarm(); const { theme, spacing, typography, layout } = useAppTheme(); const { submitting, run } = useAuthSubmission(); const [token, setToken] = useState(initialToken); const [feedback, setFeedback] = useState(null);
  const accept = async () => { const value = token.trim(); if (value.length < 32 || value.length > 512) return setFeedback("Enter the complete invitation code."); setFeedback(null); const result = await run(() => api.accept(value)); if (result.error) return setFeedback(staffErrorMessage(result.error, { invitation: true, ambiguous: result.error?.code === "TIMEOUT" || result.error?.category === "network" })); try { const accepted = requireInvitationAcceptance(result.value); setToken(""); await farm.refreshFarms(); onAccepted?.(accepted); } catch (error) { setFeedback(error?.message?.includes("acceptance") ? "The acceptance response could not be verified. Refresh your farms before retrying." : "Farm membership is being refreshed. Please retry from your dashboard."); } };
  return <Screen style={{ backgroundColor: theme.colors.background }}><ScrollView contentContainerStyle={{ width: "100%", alignSelf: "center", maxWidth: layout.formMaxWidth, padding: spacing.xl }}><Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>Join a farm</Text><Text style={{ color: theme.colors.textSecondary, marginTop: spacing.sm }}>Enter the invitation code sent to your verified email address.</Text><AppCard style={{ marginTop: spacing.xl }}><View style={{ gap: spacing.lg }}>{feedback ? <InlineFeedback type="error" message={feedback} /> : null}<AppInput label="Invitation code" value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false} testID="accept-invitation-token" required /><AppButton title="Accept invitation" onPress={accept} loading={submitting} disabled={submitting} testID="accept-invitation-submit" /></View></AppCard></ScrollView></Screen>;
}
