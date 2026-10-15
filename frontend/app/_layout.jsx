import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { ThemeProvider, useAppTheme } from "../src/theme/ThemeProvider";

function ThemeLoadingView() {
  const { theme, spacing, typography } = useAppTheme();

  return (
    <View
      accessibilityLabel="Loading saved appearance"
      accessibilityLiveRegion="polite"
      style={[styles.loading, { backgroundColor: theme.colors.background }]}
    >
      <View style={[styles.brandMark, { backgroundColor: theme.colors.primary }]}>
        <Text style={[styles.brandText, { color: theme.colors.onPrimary }]}>ICMS</Text>
      </View>
      <ActivityIndicator color={theme.colors.primary} style={{ marginTop: spacing.xl }} />
      <Text
        style={{
          color: theme.colors.textSecondary,
          fontSize: typography.sizes.small,
          marginTop: spacing.md,
        }}
      >
        Restoring your appearance
      </Text>
    </View>
  );
}

function ThemedNavigation() {
  const { theme, isThemeReady } = useAppTheme();

  if (!isThemeReady) return <ThemeLoadingView />;

  return (
    <>
      <StatusBar style="light" backgroundColor={theme.colors.primaryDark} />
      <Stack
        screenOptions={{
          contentStyle: { backgroundColor: theme.colors.background },
          headerStyle: { backgroundColor: theme.colors.primary },
          headerTintColor: theme.colors.onPrimary,
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "ICMS Design Preview" }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <ThemedNavigation />
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  brandMark: { width: 76, height: 76, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  brandText: { fontSize: 21, fontWeight: "800", letterSpacing: 1 },
});
