import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";

import { StartupGate } from "../src/navigation/StartupGate";
import { AuthProvider, useAuth } from "../src/features/auth/context/AuthProvider";
import { SessionUnavailableScreen } from "../src/features/auth/screens/SessionUnavailableScreen";
import { FarmProvider } from "../src/features/farms/context/FarmProvider";
import { canAccessProtectedRoutes, canAccessPublicAuthRoutes } from "../src/navigation/sessionPolicy";
import { ThemeProvider, useAppTheme } from "../src/theme/ThemeProvider";

void SplashScreen.preventAutoHideAsync().catch(() => {});

export function ThemedNavigation() {
  const { theme, isThemeReady } = useAppTheme();
  const auth = useAuth();
  const ready = isThemeReady && !auth.isInitializing;

  return (
    <StartupGate ready={ready}>
      <StatusBar style="light" backgroundColor={theme.colors.primaryDark} />
      {auth.status === "verification-unavailable" ? <SessionUnavailableScreen /> : <Stack
        screenOptions={{
          contentStyle: { backgroundColor: theme.colors.background },
          headerStyle: { backgroundColor: theme.colors.primary },
          headerTintColor: theme.colors.onPrimary,
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        <Stack.Protected guard={canAccessPublicAuthRoutes(auth.status)}>
          <Stack.Screen name="index" options={{ headerShown: false, title: "Welcome" }} />
          <Stack.Screen name="auth/login" options={{ title: "Log In", headerBackTitle: "Welcome" }} />
          <Stack.Screen name="auth/signup" options={{ title: "Get Started", headerBackTitle: "Welcome" }} />
          <Stack.Screen name="auth/forgot-password" options={{ title: "Forgot Password", headerBackTitle: "Log In" }} />
        </Stack.Protected>
        <Stack.Protected guard={canAccessProtectedRoutes(auth.status)}>
          <Stack.Screen name="dashboard" options={{ headerShown: false, title: "ICMS Dashboard" }} />
          <Stack.Screen name="farm/create" options={{ title: "Create Farm", headerBackTitle: "Dashboard" }} />
          <Stack.Screen name="farm/select" options={{ title: "Select Farm", headerBackTitle: "Dashboard" }} />
          <Stack.Screen name="farm/details" options={{ title: "Farm Details", headerBackTitle: "Dashboard" }} />
          <Stack.Screen name="farm/staff" options={{ title: "Staff", headerBackTitle: "Dashboard" }} />
          <Stack.Screen name="farm/staff/invite" options={{ title: "Invite Staff", headerBackTitle: "Staff" }} />
          <Stack.Screen name="cattle/index" options={{ headerShown: false, title: "Cattle" }} />
          <Stack.Screen name="cattle/register" options={{ headerShown: false, title: "Register Cattle" }} />
          <Stack.Screen name="cattle/[id]/index" options={{ headerShown: false, title: "Cattle Profile" }} />
          <Stack.Screen name="cattle/[id]/edit" options={{ headerShown: false, title: "Edit Cattle" }} />
          <Stack.Screen name="feed/index" options={{ headerShown: false, title: "Feed & Nutrition" }} />
          <Stack.Screen name="feed/inventory" options={{ headerShown: false, title: "Feed Inventory" }} />
          <Stack.Screen name="feed/schedules" options={{ headerShown: false, title: "Feeding Schedules" }} />
          <Stack.Screen name="feed/records" options={{ headerShown: false, title: "Daily Feeding" }} />
          <Stack.Screen name="feed/purchases" options={{ headerShown: false, title: "Feed Purchases" }} />
          <Stack.Screen name="feed/alerts" options={{ headerShown: false, title: "Low Stock Alerts" }} />
          <Stack.Screen name="feed/nutrition" options={{ headerShown: false, title: "Nutrition Plans" }} />
          <Stack.Screen name="feed/reports" options={{ headerShown: false, title: "Feed Reports" }} />
          <Stack.Screen name="breeding/index" options={{ headerShown: false, title: "Breeding & Genetics" }} />
          <Stack.Screen name="breeding/heat" options={{ headerShown: false, title: "Heat Cycles" }} />
          <Stack.Screen name="breeding/events" options={{ headerShown: false, title: "Breeding Events" }} />
          <Stack.Screen name="breeding/pregnancy" options={{ headerShown: false, title: "Pregnancy Tracking" }} />
          <Stack.Screen name="breeding/calving" options={{ headerShown: false, title: "Calving" }} />
          <Stack.Screen name="breeding/offspring" options={{ headerShown: false, title: "Register Offspring" }} />
          <Stack.Screen name="breeding/pedigree" options={{ headerShown: false, title: "Pedigree" }} />
          <Stack.Screen name="breeding/calendar" options={{ headerShown: false, title: "Breeding Calendar" }} />
          <Stack.Screen name="breeding/reports" options={{ headerShown: false, title: "Breeding Reports" }} />
          <Stack.Screen name="breeding/settings" options={{ headerShown: false, title: "Breeding Reminders" }} />
          <Stack.Screen name="breeding/treatments" options={{ headerShown: false, title: "Reproductive Treatments" }} />
          <Stack.Screen name="marketplace/index" options={{ headerShown: false, title: "Cattle Marketplace" }} />
          <Stack.Screen name="marketplace/[id]/index" options={{ headerShown: false, title: "Marketplace Listing" }} />
          <Stack.Screen name="marketplace/create" options={{ headerShown: false, title: "Create Listing" }} />
          <Stack.Screen name="marketplace/[id]/edit" options={{ headerShown: false, title: "Edit Listing" }} />
          <Stack.Screen name="marketplace/seller" options={{ headerShown: false, title: "Seller Dashboard" }} />
          <Stack.Screen name="marketplace/my-listings" options={{ headerShown: false, title: "My Listings" }} />
          <Stack.Screen name="marketplace/inquiries" options={{ headerShown: false, title: "My Inquiries" }} />
          <Stack.Screen name="marketplace/seller-inquiries" options={{ headerShown: false, title: "Seller Inbox" }} />
          <Stack.Screen name="marketplace/inquiry/[id]" options={{ headerShown: false, title: "Marketplace Conversation" }} />
          <Stack.Screen name="marketplace/saved" options={{ headerShown: false, title: "Saved Listings" }} />
          <Stack.Screen name="marketplace/[id]/sale" options={{ headerShown: false, title: "Confirm Sale" }} />
          <Stack.Screen name="marketplace/[id]/report" options={{ headerShown: false, title: "Report Listing" }} />
          <Stack.Screen name="marketplace/notifications" options={{ headerShown: false, title: "Marketplace Notifications" }} />
          <Stack.Screen name="marketplace/reports" options={{ headerShown: false, title: "Marketplace Reports" }} />
          <Stack.Screen name="marketplace/moderation" options={{ headerShown: false, title: "Marketplace Moderation" }} />
          <Stack.Screen name="invitations/accept" options={{ title: "Join Farm", headerBackTitle: "Dashboard" }} />
          <Stack.Screen name="session" options={{ headerShown: false, title: "Session" }} />
          <Stack.Screen name="profile" options={{ headerShown: false, title: "Profile" }} />
          <Stack.Screen name="farm/[module]" options={{ title: "Farm Module", headerBackTitle: "Dashboard" }} />
        </Stack.Protected>
        <Stack.Screen name="auth/verify-email" options={{ title: "Verify Email", headerBackTitle: "Back" }} />
        <Stack.Screen name="reset-password" options={{ title: "Reset Password", headerBackTitle: "Log In" }} />
        <Stack.Screen name="dev/design-system" options={{ title: "ICMS Design System" }} />
        <Stack.Screen name="+not-found" options={{ headerShown: false, title: "Not Found" }} />
      </Stack>
      }
    </StartupGate>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <FarmProvider>
          <ThemedNavigation />
        </FarmProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
