import { useState } from "react";
import { StyleSheet, useWindowDimensions, View } from "react-native";

import { AppButton } from "../../../components/ui/AppButton";
import { ConfirmationDialog } from "../../../components/ui/ConfirmationDialog";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { InlineFeedback } from "../../../components/ui/InlineFeedback";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { ShowcaseSection } from "./ShowcaseSection";

export function FeedbackShowcase() {
  const { width } = useWindowDimensions();
  const { spacing, layout } = useAppTheme();
  const [dialogVisible, setDialogVisible] = useState(false);
  const [confirmationMessage, setConfirmationMessage] = useState("");
  const multiColumn = width >= layout.breakpoints.tablet;

  const confirmPreview = () => {
    setDialogVisible(false);
    setConfirmationMessage("Confirmation preview completed. No application record was changed.");
  };

  return (
    <ShowcaseSection
      title="Feedback and confirmations"
      description="Central states give users clear progress, recovery, empty-content, success, and confirmation experiences."
      entranceDelay={210}
    >
      <View style={[styles.grid, { gap: spacing.md }]}>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <FeedbackState type="loading" title="Loading herd summary" compact showSkeleton />
        </View>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <FeedbackState type="empty" title="No health alerts" message="New alerts will appear here when attention is required." compact />
        </View>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <FeedbackState type="error" title="Unable to refresh" message="The sample request could not be completed." actionLabel="Retry preview" onAction={() => setConfirmationMessage("Retry preview selected. No network request was made.")} compact />
        </View>
        <View style={multiColumn ? styles.gridItem : styles.fullItem}>
          <FeedbackState type="success" title="Vaccination recorded" message="Success feedback is concise and does not interrupt the workflow." compact />
        </View>
      </View>
      <AppButton
        title="Open confirmation preview"
        variant="outline"
        onPress={() => setDialogVisible(true)}
        style={{ marginTop: spacing.lg }}
      />
      <InlineFeedback type="success" message={confirmationMessage} />
      <ConfirmationDialog
        visible={dialogVisible}
        title="Confirm preview action"
        message="This demonstrates the shared confirmation dialog. It will not create, update, or delete any record."
        confirmLabel="Confirm preview"
        onConfirm={confirmPreview}
        onCancel={() => setDialogVisible(false)}
      />
    </ShowcaseSection>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap" },
  gridItem: { flexGrow: 1, flexBasis: "46%", minWidth: 260 },
  fullItem: { width: "100%" },
});
