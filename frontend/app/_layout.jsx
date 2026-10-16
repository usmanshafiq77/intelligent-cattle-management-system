import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";

import { StartupGate } from "../src/navigation/StartupGate";
import { AuthProvider } from "../src/features/auth/context/AuthProvider";
import { ThemeProvider, useAppTheme } from "../src/theme/ThemeProvider";

void SplashScreen.preventAutoHideAsync().catch(() => {});

export function ThemedNavigation() {
  const { theme, isThemeReady } = useAppTheme();

  return (
    <StartupGate ready={isThemeReady}>
      <StatusBar style="light" backgroundColor={theme.colors.primaryDark} />
      <Stack
        screenOptions={{
          contentStyle: { backgroundColor: theme.colors.background },
          headerStyle: { backgroundColor: theme.colors.primary },
          headerTintColor: theme.colors.onPrimary,
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false, title: "Welcome" }} />
        <Stack.Screen name="auth/login" options={{ title: "Log In", headerBackTitle: "Welcome" }} />
        <Stack.Screen name="auth/signup" options={{ title: "Get Started", headerBackTitle: "Welcome" }} />
        <Stack.Screen name="dev/design-system" options={{ title: "ICMS Design System" }} />
        <Stack.Screen name="+not-found" options={{ headerShown: false, title: "Not Found" }} />
      </Stack>
    </StartupGate>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ThemedNavigation />
      </AuthProvider>
    </ThemeProvider>
  );
}
