import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useEffect } from "react";
import * as SplashScreen from "expo-splash-screen";

import { BrandMark } from "../components/brand/BrandMark";
import { useAppTheme } from "../theme/ThemeProvider";

export function StartupGate({ ready, children, hideSplash = SplashScreen.hideAsync }) {
  const { theme, spacing, typography } = useAppTheme();

  useEffect(() => {
    if (!ready) return;
    void hideSplash().catch(() => {});
  }, [hideSplash, ready]);

  if (ready) return <>{children}</>;

  return (
    <View
      accessibilityLabel="Preparing ICMS"
      accessibilityLiveRegion="polite"
      style={[styles.loading, { backgroundColor: theme.colors.primaryDark }]}
    >
      <BrandMark size={82} inverse />
      <ActivityIndicator color={theme.colors.onPrimary} style={{ marginTop: spacing.xl }} />
      <Text style={{ color: theme.colors.onPrimary, fontSize: typography.sizes.small, marginTop: spacing.md }}>
        Preparing your workspace
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
});
