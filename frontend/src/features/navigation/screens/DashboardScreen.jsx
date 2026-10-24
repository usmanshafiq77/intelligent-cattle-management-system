
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";

import { cattleApi } from "../../../api/cattle";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { Screen } from "../../../components/ui/Screen";
import { StatusBadge } from "../../../components/ui/StatusBadge";

import { useAuth } from "../../auth/context/AuthProvider";
import { FarmSelector } from "../../farms/components/FarmSelector";
import { useFarm } from "../../farms/context/FarmProvider";

import { platformNavigationItems } from "../../permissions/navigationConfig";

import { roleLabel } from "../../permissions/permissionCatalog";
import { useAppTheme } from "../../../theme/ThemeProvider";

// Existing role-specific dashboard components
import { OwnerDashboard } from "../dashboards/OwnerDashboard";
import { WorkerDashboard } from "../dashboards/WorkerDashboard";
import { VeterinarianDashboard } from "../dashboards/VeterinarianDashboard";

// =====================================================
// THEME CONTROLS
// =====================================================

function ThemeControls() {
  const {
    theme,
    themes,
    changeTheme,
    radius,
    spacing,
    typography,
  } = useAppTheme();

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel="Color theme"
      style={styles.themeOptions}
    >
      {Object.values(themes).map((option) => (
        <Pressable
          key={option.id}
          testID={`theme-option-${option.id}`}
          accessibilityRole="radio"
          accessibilityLabel={`Use ${option.name} theme`}
          accessibilityState={{
            checked: option.id === theme.id,
          }}
          onPress={() => {
            void changeTheme(option.id).catch(() => {});
          }}
          style={({ pressed }) => ({
            width: 44,
            height: 44,
            alignItems: "center",
            justifyContent: "center",
            borderWidth: option.id === theme.id ? 2 : 1,
            borderColor:
              option.id === theme.id
                ? theme.colors.primary
                : theme.colors.border,
            backgroundColor: theme.colors.surface,
            borderRadius: radius.pill,
            opacity: pressed ? 0.75 : 1,
          })}
        >
          <View style={[styles.themePreview, { backgroundColor: option.colors.background, borderColor: option.colors.border }]}>
            <View style={[styles.themePreviewHalf, { backgroundColor: option.colors.primary }]} />
            <View style={[styles.themePreviewHalf, { backgroundColor: option.colors.secondary }]} />
          </View>
          {option.id === theme.id ? <View testID={`theme-selected-${option.id}`} style={[styles.themeCheck, { backgroundColor: theme.colors.primary }]}><Text style={styles.themeCheckText}>✓</Text></View> : null}
        </Pressable>
      ))}
    </View>
  );
}

// =====================================================
// MAIN DASHBOARD SCREEN
// =====================================================

export function DashboardScreen({
  onNavigate,
  api = cattleApi,
}) {
  const auth = useAuth();
  const farm = useFarm();

  const { width } = useWindowDimensions();

  const {
    theme,
    spacing,
    typography,
    layout,
  } = useAppTheme();

  const desktop = width >= layout.breakpoints.tablet;

  const platformItems = platformNavigationItems(auth.user);

  // The role belongs to the active farm membership.
  const activeRole = farm.membership?.role;

  // =====================================================
  // ROLE-SPECIFIC DASHBOARDS
  // =====================================================

  const renderRoleDashboard = () => {
    if (activeRole === "FARM_OWNER") {
      return (
        <OwnerDashboard
          key={`${farm.activeFarm?.id}:owner`}
          farm={farm}
          onNavigate={onNavigate}
          api={api}
        />
      );
    }

    if (activeRole === "WORKER") {
      return (
        <WorkerDashboard
          key={`${farm.activeFarm?.id}:worker`}
          farm={farm}
          onNavigate={onNavigate}
          api={api}
        />
      );
    }

    if (activeRole === "VETERINARIAN") {
      return (
        <VeterinarianDashboard
          key={`${farm.activeFarm?.id}:veterinarian`}
          farm={farm}
          onNavigate={onNavigate}
          api={api}
        />
      );
    }

    // Never grant owner controls to unknown roles.
    return (
      <FeedbackState
        type="error"
        title="Unsupported farm role"
        message="Your active farm membership role could not be recognized. Please contact the farm administrator."
      />
    );
  };

  // =====================================================
  // FARM CONTENT AND MEMBERSHIP STATES
  // =====================================================

  const farmContent = () => {
    // Loading memberships and permissions
    if (
      [
        "loading",
        "loading-permissions",
        "creating",
      ].includes(farm.status)
    ) {
      return (
        <FeedbackState
          type="loading"
          title="Verifying farm access"
          message="Loading active memberships and effective permissions."
          showSkeleton
        />
      );
    }

    // Farm access errors
    if (
      [
        "unavailable",
        "permission-unavailable",
      ].includes(farm.status)
    ) {
      return (
        <FeedbackState
          type="error"
          title="Farm access unavailable"
          message={farm.issue?.message}
          actionLabel="Retry"
          onAction={() => {
            void farm.refreshFarms();
          }}
        />
      );
    }

    // ===================================================
    // NO FARMS: CREATE OR JOIN AN EXISTING FARM
    // ===================================================

    if (farm.status === "no-farms") {
      return (
        <View style={{ gap: spacing.md }}>
          <FeedbackState
            title="No accessible farms"
            message={
              auth.user?.is_system_admin
                ? "This system administrator has no active farm membership. Platform access remains separate."
                : "You do not currently have an active farm membership."
            }
          />

          <AppButton
            title="Join Existing Farm"
            variant="secondary"
            onPress={() => {
              onNavigate("/invitations/accept");
            }}
          />

          <AppButton
            title="Create Farm"
            onPress={() => {
              onNavigate("/farm/create");
            }}
          />
        </View>
      );
    }

    // User has several farms but none selected
    if (farm.status === "selection-required") {
      return (
        <FeedbackState
          title="Choose your farm"
          message="You belong to multiple farms. Select one above to verify its role and permissions."
        />
      );
    }

    if (farm.status !== "ready") {
      return null;
    }

    // Safely handle unexpected incomplete farm state
    if (!farm.activeFarm?.id || !farm.membership) {
      return (
        <FeedbackState
          type="error"
          title="Farm membership unavailable"
          message="The selected farm or its membership information is missing."
          actionLabel="Refresh farms"
          onAction={() => {
            void farm.refreshFarms();
          }}
        />
      );
    }

    // ===================================================
    // ACTIVE FARM
    // ===================================================

    return (
      <View style={{ gap: spacing.xl }}>
        {/* CURRENT FARM INFORMATION */}

        <View style={styles.activeFarmTitle}>
          <View style={styles.grow}>
            <Text
              accessibilityRole="header"
              style={{
                color: theme.colors.text,
                fontSize: typography.sizes.title,
                fontWeight: typography.weights.extrabold,
              }}
            >
              {farm.activeFarm.name}
            </Text>

            <Text
              style={{
                color: theme.colors.textSecondary,
                marginTop: spacing.xs,
              }}
            >
              {roleLabel(activeRole)}
              {" · active membership"}
            </Text>
          </View>

          <StatusBadge
            status="success"
            label="Verified"
          />
        </View>

        {/*
          Existing farm details and switching actions
          remain available for active Workers/Vets.

          The Owner dashboard already contains
          its own management buttons.
        */}

        {activeRole === "WORKER" ||
        activeRole === "VETERINARIAN" ? (
          <View style={styles.contextActions}>
            <AppButton
              title="Farm details"
              variant="outline"
              size="small"
              fullWidth={false}
              onPress={() => {
                onNavigate("/farm/details");
              }}
            />

            {farm.farms.length > 1 ? (
              <AppButton
                title="Switch farm"
                variant="outline"
                size="small"
                fullWidth={false}
                onPress={() => {
                  onNavigate("/farm/select");
                }}
              />
            ) : null}
          </View>
        ) : null}

        {/* =================================================
            RENDER DASHBOARD BASED ON ROLE
        ================================================= */}

        {renderRoleDashboard()}
      </View>
    );
  };

  // =====================================================
  // MAIN SCREEN RENDER
  // =====================================================

  return (
    <Screen
      style={[
        styles.screen,
        {
          backgroundColor: theme.colors.background,
        },
      ]}
    >
      {/* =================================================
          MAIN BODY
      ================================================= */}

      <View style={styles.body}>
        {/* MAIN CONTENT */}

        <ScrollView
          style={styles.grow}
          contentContainerStyle={[
            styles.content,
            {
              maxWidth: layout.contentMaxWidth,
              padding: desktop
                ? spacing.xxl
                : spacing.lg,
            },
          ]}
        >
          <View testID="dashboard-theme-selector" style={[styles.themeSelectorRow, { marginBottom: spacing.md }]}>
            <ThemeControls />
          </View>

          {/* DASHBOARD INTRODUCTION */}

          <Text
            style={{
              color: theme.colors.primary,
              fontSize: typography.sizes.caption,
              fontWeight: typography.weights.extrabold,
              letterSpacing:
                typography.letterSpacing.eyebrow,
            }}
          >
            ICMS FARM OVERVIEW
          </Text>

          <Text
            accessibilityRole="header"
            style={{
              color: theme.colors.text,
              fontSize: typography.sizes.heading,
              lineHeight: typography.lineHeights.heading,
              fontWeight: typography.weights.extrabold,
              marginTop: spacing.xs,
            }}
          >
            Welcome, {auth.user?.full_name || "farm operator"}
          </Text>

          <Text
            style={{
              color: theme.colors.textSecondary,
              marginTop: spacing.sm,
              marginBottom: spacing.xl,
            }}
          >
            Real farm and herd data, scoped by your verified membership.
          </Text>

          {/* =================================================
              FARM SELECTOR
          ================================================= */}

          {farm.farms.length ? (
            <FarmSelector
              farms={farm.farms}
              activeFarmId={farm.activeFarm?.id}
              disabled={farm.isLoading}
              onSelect={(farmId) => {
                void farm.selectFarm(farmId);
              }}
            />
          ) : null}

          {/* =================================================
              MAIN FARM CONTENT
          ================================================= */}

          <View style={{ marginTop: spacing.xxl }}>
            {farmContent()}
          </View>

          {/* =================================================
              SYSTEM ADMINISTRATION
          ================================================= */}

          {platformItems.length ? (
            <View
              style={{
                marginTop: spacing.xxl,
                gap: spacing.md,
              }}
            >
              <Text
                accessibilityRole="header"
                style={{
                  color: theme.colors.text,
                  fontSize: typography.sizes.title,
                  fontWeight: typography.weights.bold,
                }}
              >
                System administration
              </Text>

              {platformItems.map((item) => (
                <AppCard key={item.key}>
                  <Text
                    style={{
                      color: theme.colors.text,
                      fontWeight: typography.weights.bold,
                    }}
                  >
                    {item.title}
                  </Text>

                  <Text
                    style={{
                      color: theme.colors.textSecondary,
                      marginTop: spacing.xs,
                    }}
                  >
                    {item.description}
                  </Text>

                  <StatusBadge
                    status="info"
                    label="UI coming soon"
                    compact
                  />
                </AppCard>
              ))}
            </View>
          ) : null}

        </ScrollView>
      </View>

    </Screen>
  );
}

// =====================================================
// STYLES
// =====================================================

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },

  body: {
    flex: 1,
    flexDirection: "row",
  },

  grow: {
    flex: 1,
  },

  content: {
    width: "100%",
    alignSelf: "center",
    paddingBottom: 48,
  },

  activeFarmTitle: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 12,
  },

  contextActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },

  themeOptions: {
    flexDirection: "row",
    gap: 8,
  },
  themeSelectorRow: {
    alignItems: "flex-end",
    width: "100%",
  },
  themePreview: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: "row",
    overflow: "hidden",
  },
  themePreviewHalf: {
    flex: 1,
  },
  themeCheck: {
    position: "absolute",
    right: -2,
    bottom: -2,
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  themeCheckText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "800",
    lineHeight: 12,
  },
});
