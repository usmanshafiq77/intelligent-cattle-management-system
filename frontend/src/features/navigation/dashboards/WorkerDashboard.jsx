
import { Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { StatCard } from "../../../components/ui/StatCard";
import { useCattleSummary } from "../../cattle/hooks/useCattleSummary";
import { cattleErrorMessage } from "../../cattle/cattleErrors";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function WorkerDashboard({
  farm,
  onNavigate,
  api = cattleApi,
}) {
  const { theme, spacing, typography } = useAppTheme();

  const farmId = farm.activeFarm?.id;
  const canViewCattle = farm.can("cattle.view");
  const canCreateCattle = farm.can("cattle.create");

  const collection = useCattleSummary({
    farmId,
    enabled: Boolean(farmId) && canViewCattle,
    api,
  });

  return (
    <View style={{ gap: spacing.xl }}>

      {/* WORKER DASHBOARD HEADING */}
      <View style={{ gap: spacing.sm }}>
        <Text
          accessibilityRole="header"
          style={{
            color: theme.colors.text,
            fontSize: typography.sizes.title,
            fontWeight: typography.weights.extrabold,
          }}
        >
          Worker Dashboard
        </Text>

        <Text
          style={{ color: theme.colors.textSecondary }}
        >
          Daily farm operations for {farm.activeFarm?.name}
        </Text>
      </View>

      {/* CATTLE STATISTICS */}
      {canViewCattle ? (
        <>
          {collection.status === "loading" && (
            <FeedbackState
              type="loading"
              title="Loading cattle statistics"
              message="Fetching your farm's cattle information."
              showSkeleton
            />
          )}

          {collection.status === "error" && (
            <FeedbackState
              type="error"
              title="Cattle statistics unavailable"
              message={cattleErrorMessage(collection.error)}
              actionLabel="Retry"
              onAction={() => {
                void collection.refresh();
              }}
            />
          )}

          {collection.status === "ready" && (
            <View
              style={{
                flexDirection: "row",
                flexWrap: "wrap",
                gap: spacing.md,
              }}
            >
              <StatCard
                label="Total Cattle"
                value={collection.summary.total}
                unit="head"
                icon="H"
                style={{ minWidth: 180, flexGrow: 1 }}
              />

              <StatCard
                label="Active Cattle"
                value={collection.summary.statusCounts.ACTIVE}
                unit="head"
                icon="A"
                status="success"
                style={{ minWidth: 180, flexGrow: 1 }}
              />
            </View>
          )}
        </>
      ) : (
        <FeedbackState
          title="Limited cattle access"
          message="You do not have permission to view cattle statistics."
        />
      )}

      {/* DAILY OPERATIONS */}
      <Text
        accessibilityRole="header"
        style={{
          color: theme.colors.text,
          fontSize: typography.sizes.subtitle,
          fontWeight: typography.weights.bold,
        }}
      >
        Daily Farm Operations
      </Text>

      {/* CATTLE RECORDS */}
      {canViewCattle && (
        <AppCard
          title="Cattle Records"
          subtitle="View and manage permitted cattle information."
        >
          <View style={{ gap: spacing.md }}>
            <AppButton
              title="View Cattle"
              onPress={() => onNavigate("/cattle")}
            />

            {canCreateCattle && (
              <AppButton
                title="Register Cattle"
                variant="outline"
                onPress={() => onNavigate("/cattle/register")}
              />
            )}
          </View>
        </AppCard>
      )}

      {/* MILK PRODUCTION */}
      <AppCard
        title="Milk Production"
        subtitle="Record daily milk production."
      >
        <View style={{ gap: spacing.md }}>
          {farm.can("milk.record") ? <AppButton title="Record Milk" onPress={() => onNavigate("/milk/entry")} /> : null}
          {farm.can("milk.view") ? <AppButton title="View Milk History" variant="outline" onPress={() => onNavigate("/milk/records")} /> : null}
        </View>
      </AppCard>

      {/* FEED MANAGEMENT */}
      <AppCard
        title="Feed Management"
        subtitle="Review schedules and record completed feeding."
      >
        <View style={{ gap: spacing.md }}>
          <AppButton title="Record Feeding" onPress={() => onNavigate("/feed/records")} />
          <AppButton title="View Feeding Schedules" variant="outline" onPress={() => onNavigate("/feed/schedules")} />
        </View>
      </AppCard>

      {/* HEALTH OBSERVATIONS */}
      <AppCard
        title="Health Observations"
        subtitle="Report unusual cattle symptoms."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Report health issues to a veterinarian.
        </Text>
      </AppCard>

      {/* DAILY TASKS */}
      <AppCard
        title="Assigned Tasks & Cattle"
        subtitle="Start or complete assigned work and review animals under your care."
      >
        <View style={{ gap: spacing.md }}>
          <AppButton title="View My Tasks" onPress={() => onNavigate("/tasks/my")} />
          <AppButton title="View Assigned Cattle" variant="outline" onPress={() => onNavigate("/tasks/assigned-cattle")} />
        </View>
      </AppCard>

      {/* REFRESH */}
      {canViewCattle && collection.status === "ready" && (
        <AppButton
          title="Refresh Cattle Overview"
          variant="outline"
          onPress={() => {
            void collection.refresh();
          }}
        />
      )}

    </View>
  );
}
