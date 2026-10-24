
import { Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { StatCard } from "../../../components/ui/StatCard";

import { useCattleSummary } from "../../cattle/hooks/useCattleSummary";
import { cattleErrorMessage } from "../../cattle/cattleErrors";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function VeterinarianDashboard({
  farm,
  onNavigate,
  api = cattleApi,
}) {
  const { theme, spacing, typography } = useAppTheme();

  const farmId = farm?.activeFarm?.id;

  const canViewCattle = farm?.can?.("cattle.view") ?? false;

  const collection = useCattleSummary({
    farmId,
    enabled: Boolean(farmId) && canViewCattle,
    api,
  });

  if (!farmId) {
    return (
      <FeedbackState
        title="No farm selected"
        message="Select a farm to access your veterinary dashboard."
      />
    );
  }

  return (
    <View style={{ gap: spacing.xl }}>

      {/* VETERINARIAN DASHBOARD HEADER */}

      <View style={{ gap: spacing.sm }}>
        <Text
          accessibilityRole="header"
          style={{
            color: theme.colors.text,
            fontSize: typography.sizes.title,
            fontWeight: typography.weights.extrabold,
          }}
        >
          Veterinarian Dashboard
        </Text>

        <Text
          style={{
            color: theme.colors.textSecondary,
          }}
        >
          Animal healthcare and veterinary monitoring for{" "}
          {farm.activeFarm.name}
        </Text>
      </View>

      {/* HERD OVERVIEW */}

      <Text
        accessibilityRole="header"
        style={{
          color: theme.colors.text,
          fontSize: typography.sizes.subtitle,
          fontWeight: typography.weights.bold,
        }}
      >
        Veterinary Herd Overview
      </Text>

      {canViewCattle ? (
        <>
          {collection.status === "loading" ? (
            <FeedbackState
              type="loading"
              title="Loading herd information"
              message="Fetching cattle statistics."
              showSkeleton
            />
          ) : null}

          {collection.status === "error" ? (
            <FeedbackState
              type="error"
              title="Herd information unavailable"
              message={cattleErrorMessage(collection.error)}
              actionLabel="Retry"
              onAction={() => {
                void collection.refresh();
              }}
            />
          ) : null}

          {collection.status === "ready" ? (
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
                style={{
                  minWidth: 180,
                  flexGrow: 1,
                }}
              />

              <StatCard
                label="Active Cattle"
                value={collection.summary.statusCounts.ACTIVE}
                unit="head"
                icon="A"
                status="success"
                style={{
                  minWidth: 180,
                  flexGrow: 1,
                }}
              />
            </View>
          ) : null}
        </>
      ) : (
        <FeedbackState
          title="Limited cattle access"
          message="You do not have permission to view cattle statistics."
        />
      )}

      {/* MEDICAL OPERATIONS */}

      <Text
        accessibilityRole="header"
        style={{
          color: theme.colors.text,
          fontSize: typography.sizes.subtitle,
          fontWeight: typography.weights.bold,
        }}
      >
        Veterinary Operations
      </Text>

      {/* CATTLE RECORDS */}

      {canViewCattle ? (
        <AppCard
          title="Cattle Health Reference"
          subtitle="Access the cattle registered on your assigned farm."
        >
          <AppButton
            title="View Cattle Records"
            onPress={() => onNavigate("/cattle")}
          />
        </AppCard>
      ) : null}

      {farm.can("feed.nutrition.view") ? (
        <AppCard
          title="Nutrition Plans"
          subtitle="Review permitted nutrition records without feed cost or administrative access."
        >
          <AppButton title="View Nutrition Plans" onPress={() => onNavigate("/feed/nutrition")} />
        </AppCard>
      ) : null}

      {/* HEALTH RECORDS */}

      <AppCard
        title="Health Records"
        subtitle="Review cattle illnesses, examinations and medical history."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Veterinary health records interface.
        </Text>
      </AppCard>

      {/* VACCINATIONS */}

      <AppCard
        title="Vaccination Management"
        subtitle="Track upcoming and completed vaccinations."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Vaccination schedules and administration records.
        </Text>
      </AppCard>

      {/* DIAGNOSIS AND TREATMENT */}

      <AppCard
        title="Diagnosis and Treatment"
        subtitle="Document medical examinations and treatment plans."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Diagnosis and treatment interface.
        </Text>
      </AppCard>

      {/* MEDICAL ALERTS */}

      <AppCard
        title="Medical Alerts"
        subtitle="Review cattle that require medical attention."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Health alerts and sick cattle monitoring.
        </Text>
      </AppCard>

      {/* FOLLOW UPS */}

      <AppCard
        title="Veterinary Follow-ups"
        subtitle="Monitor follow-up examinations and recovery."
      >
        <Text style={{ color: theme.colors.textSecondary }}>
          Coming Soon — Veterinary appointments and follow-ups.
        </Text>
      </AppCard>

      {/* REFRESH */}

      {canViewCattle && collection.status === "ready" ? (
        <AppButton
          title="Refresh Herd Overview"
          variant="outline"
          onPress={() => {
            void collection.refresh();
          }}
        />
      ) : null}

    </View>
  );
}
