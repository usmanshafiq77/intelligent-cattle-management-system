
import { Text, View } from "react-native";

import { cattleApi } from "../../../api/cattle";

import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { StatCard } from "../../../components/ui/StatCard";
import { StatusBadge } from "../../../components/ui/StatusBadge";

import { useCattleSummary } from "../../cattle/hooks/useCattleSummary";
import { cattleErrorMessage } from "../../cattle/cattleErrors";
import { optionLabel } from "../../cattle/cattleOptions";

import { farmNavigationItems } from "../../permissions/navigationConfig";
import { useAppTheme } from "../../../theme/ThemeProvider";

export function OwnerDashboard({
  farm,
  onNavigate,
  api = cattleApi,
}) {
  const { theme, spacing, typography } = useAppTheme();

  const farmId = farm.activeFarm?.id;

  const canViewCattle = farm.can("cattle.view");
  const canCreateCattle = farm.can("cattle.create");
  const canViewStaff = farm.can("staff.view");
  const canManageStaff = farm.can("staff.manage");

  const modules = farmNavigationItems(farm.can);

  const collection = useCattleSummary({
    farmId,
    enabled: Boolean(farmId) && canViewCattle,
    api,
  });

  if (!farmId) {
    return (
      <FeedbackState
        title="No farm selected"
        message="Please select a farm to access the owner dashboard."
      />
    );
  }

  const summary =
    collection.status === "ready"
      ? collection.summary
      : null;

  const statusCounts = summary
    ? Object.fromEntries(
        Object.entries(summary.statusCounts).filter(
          ([, count]) => count > 0
        )
      )
    : {};

  return (
    <View style={{ gap: spacing.xxl }}>

      {/* OWNER DASHBOARD HEADER */}

      <View style={{ gap: spacing.sm }}>
        <Text
          accessibilityRole="header"
          style={{
            color: theme.colors.text,
            fontSize: typography.sizes.title,
            fontWeight: typography.weights.extrabold,
          }}
        >
          Farm Owner Dashboard
        </Text>

        <Text
          style={{
            color: theme.colors.textSecondary,
          }}
        >
          Manage your farm, livestock, staff and operations.
        </Text>

        <StatusBadge
          status="success"
          label="Farm Owner"
          compact
        />
      </View>

      {/* FARM MANAGEMENT ACTIONS */}

      <AppCard
        title={farm.activeFarm.name}
        subtitle="Farm management and administration"
      >
        <View
          style={{
            flexDirection: "row",
            flexWrap: "wrap",
            gap: spacing.md,
          }}
        >
          <AppButton
            title="Farm Details"
            variant="outline"
            fullWidth={false}
            onPress={() => onNavigate("/farm/details")}
          />

          <AppButton
            title="Add Farm"
            variant="outline"
            fullWidth={false}
            onPress={() => onNavigate("/farm/create")}
          />

          {farm.farms.length > 1 ? (
            <AppButton
              title="Switch Farm"
              variant="outline"
              fullWidth={false}
              onPress={() => onNavigate("/farm/select")}
            />
          ) : null}
        </View>
      </AppCard>

      {/* HERD OVERVIEW */}

      <Text
        accessibilityRole="header"
        style={{
          color: theme.colors.text,
          fontSize: typography.sizes.subtitle,
          fontWeight: typography.weights.bold,
        }}
      >
        Farm Herd Overview
      </Text>

      {!canViewCattle ? (
        <FeedbackState
          title="Cattle overview unavailable"
          message="Your current membership does not include permission to view cattle statistics."
        />
      ) : null}

      {canViewCattle &&
      collection.status === "loading" ? (
        <FeedbackState
          type="loading"
          title="Loading herd overview"
          message="Fetching farm cattle statistics."
          showSkeleton
        />
      ) : null}

      {canViewCattle &&
      collection.status === "error" ? (
        <FeedbackState
          type="error"
          title="Herd overview unavailable"
          message={cattleErrorMessage(collection.error)}
          actionLabel="Retry"
          onAction={() => {
            void collection.refresh();
          }}
        />
      ) : null}

      {canViewCattle && summary ? (
        <>
          {/* REAL CATTLE STATISTICS */}

          <View
            style={{
              flexDirection: "row",
              flexWrap: "wrap",
              gap: spacing.md,
            }}
          >
            <StatCard
              label="Total Cattle"
              value={summary.total}
              unit="head"
              icon="H"
              style={{
                minWidth: 180,
                flexGrow: 1,
              }}
            />

            <StatCard
              label="Active Cattle"
              value={summary.statusCounts.ACTIVE}
              unit="head"
              icon="A"
              status="success"
              style={{
                minWidth: 180,
                flexGrow: 1,
              }}
            />

            <StatCard
              label="Female Cattle"
              value={summary.femaleCount}
              unit="head"
              icon="F"
              style={{
                minWidth: 180,
                flexGrow: 1,
              }}
            />

            <StatCard
              label="Male Cattle"
              value={summary.maleCount}
              unit="head"
              icon="M"
              style={{
                minWidth: 180,
                flexGrow: 1,
              }}
            />

            <StatCard
              label="Breeds Represented"
              value={summary.breedCount}
              icon="B"
              style={{
                minWidth: 180,
                flexGrow: 1,
              }}
            />
          </View>

          {/* CATTLE LIFECYCLE SUMMARY */}

          {summary.total > 0 ? (
            <AppCard
              title="Herd by Lifecycle Status"
              subtitle="Current cattle status distribution."
            >
              <View style={{ gap: spacing.md }}>
                {Object.entries(statusCounts)
                  .sort(([a], [b]) =>
                    a.localeCompare(b)
                  )
                  .map(([status, count]) => (
                    <View
                      key={status}
                      style={{
                        flexDirection: "row",
                        alignItems: "center",
                        gap: spacing.md,
                      }}
                    >
                      <Text
                        style={{
                          color: theme.colors.text,
                          minWidth: 95,
                          fontWeight:
                            typography.weights.semibold,
                        }}
                      >
                        {optionLabel(status)}
                      </Text>

                      <View
                        style={{
                          flex: 1,
                          height: 10,
                          borderRadius: 8,
                          overflow: "hidden",
                          backgroundColor:
                            theme.colors.surfaceSecondary,
                        }}
                      >
                        <View
                          style={{
                            height: "100%",
                            backgroundColor:
                              theme.colors.primary,
                            width: `${
                              Math.max(
                                4,
                                (count / summary.total) * 100
                              )
                            }%`,
                          }}
                        />
                      </View>

                      <Text
                        style={{
                          color:
                            theme.colors.textSecondary,
                          minWidth: 30,
                          textAlign: "right",
                        }}
                      >
                        {count}
                      </Text>
                    </View>
                  ))}
              </View>
            </AppCard>
          ) : (
            <FeedbackState
              title="No cattle registered"
              message="Register the first animal to begin tracking your herd."
              actionLabel={
                canCreateCattle
                  ? "Register Cattle"
                  : undefined
              }
              onAction={
                canCreateCattle
                  ? () => onNavigate("/cattle/register")
                  : undefined
              }
            />
          )}

          {/* CATTLE QUICK ACTIONS */}

          <View
            style={{
              flexDirection: "row",
              flexWrap: "wrap",
              gap: spacing.md,
            }}
          >
            <AppButton
              title="View Cattle"
              fullWidth={false}
              onPress={() => onNavigate("/cattle")}
            />

            {canCreateCattle ? (
              <AppButton
                title="Register Cattle"
                variant="secondary"
                fullWidth={false}
                onPress={() =>
                  onNavigate("/cattle/register")
                }
              />
            ) : null}

            <AppButton
              title="Refresh Overview"
              variant="outline"
              fullWidth={false}
              onPress={() => {
                void collection.refresh();
              }}
            />
          </View>
        </>
      ) : null}

      {/* STAFF MANAGEMENT */}

      {canViewStaff || canManageStaff ? (
        <>
          <Text
            accessibilityRole="header"
            style={{
              color: theme.colors.text,
              fontSize: typography.sizes.subtitle,
              fontWeight: typography.weights.bold,
            }}
          >
            Staff Management
          </Text>

          <AppCard
            title="Farm Team"
            subtitle="Manage authorized workers and veterinarians."
          >
            <View
              style={{
                flexDirection: "row",
                flexWrap: "wrap",
                gap: spacing.md,
              }}
            >
              {canViewStaff ? (
                <AppButton
                  title="View Staff"
                  fullWidth={false}
                  onPress={() =>
                    onNavigate("/farm/staff")
                  }
                />
              ) : null}

              {canManageStaff ? (
                <AppButton
                  title="Invite Staff"
                  variant="outline"
                  fullWidth={false}
                  onPress={() =>
                    onNavigate("/farm/staff/invite")
                  }
                />
              ) : null}
            </View>
          </AppCard>
        </>
      ) : null}

      {/* AVAILABLE FARM MODULES */}

      {modules.length > 0 ? (
        <>
          <Text
            accessibilityRole="header"
            style={{
              color: theme.colors.text,
              fontSize: typography.sizes.subtitle,
              fontWeight: typography.weights.bold,
            }}
          >
            Farm Management Modules
          </Text>

          <View
            style={{
              flexDirection: "row",
              flexWrap: "wrap",
              gap: spacing.md,
            }}
          >
            {modules.map((item) => (
              <AppCard
                key={item.key}
                style={{
                  minWidth: 240,
                  flexGrow: 1,
                  flexBasis: 280,
                  gap: spacing.md,
                }}
              >
                <Text
                  style={{
                    color: theme.colors.text,
                    fontSize:
                      typography.sizes.subtitle,
                    fontWeight:
                      typography.weights.bold,
                  }}
                >
                  {item.title}
                </Text>

                <Text
                  style={{
                    color: theme.colors.textSecondary,
                  }}
                >
                  {item.description}
                </Text>

                <StatusBadge
                  status={
                    item.comingSoon
                      ? "info"
                      : "success"
                  }
                  label={
                    item.comingSoon
                      ? "Coming soon"
                      : "Available"
                  }
                  compact
                />

                <AppButton
                  title={
                    item.comingSoon
                      ? "View module status"
                      : `Open ${item.title}`
                  }
                  variant="outline"
                  size="small"
                  onPress={() =>
                    onNavigate(item.href)
                  }
                />
              </AppCard>
            ))}
          </View>
        </>
      ) : null}

    </View>
  );
}
