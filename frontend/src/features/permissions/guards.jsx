import { View } from "react-native";

import { FeedbackState } from "../../components/ui/FeedbackState";
import { useFarm } from "../farms/context/FarmProvider";

export function RequireFarm({ children }) {
  const farm = useFarm();
  if (farm.status === "ready" && farm.activeFarm) return children;
  if (farm.isLoading) return <FeedbackState type="loading" title="Verifying farm access" message="Checking your active membership and permissions." showSkeleton />;
  if (farm.status === "selection-required") return <FeedbackState title="Choose a farm" message="Select one of your verified farms from the dashboard before opening a farm module." />;
  if (farm.status === "no-farms") return <FeedbackState title="No accessible farms" message="No active farm membership is available for this account." />;
  return <FeedbackState type="error" title="Farm access unavailable" message={farm.issue?.message} actionLabel="Retry" onAction={() => { void farm.refreshFarms(); }} />;
}

export function RequirePermission({ permission, children }) {
  const farm = useFarm();
  if (farm.status !== "ready" || !farm.activeFarm) return <RequireFarm>{children}</RequireFarm>;
  if (typeof permission !== "string" || !farm.can(permission)) {
    return (
      <View accessibilityRole="alert">
        <FeedbackState type="error" title="Access denied" message="Your verified permissions do not allow access to this area." />
      </View>
    );
  }
  return children;
}

export function useCan(permission) {
  const farm = useFarm();
  return farm.status === "ready" && farm.can(permission);
}

export function useActiveFarm() {
  const farm = useFarm();
  return farm.status === "ready" ? farm.activeFarm : null;
}
