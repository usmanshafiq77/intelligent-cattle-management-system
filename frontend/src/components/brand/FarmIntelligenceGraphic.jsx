import { StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useAppTheme } from "../../theme/ThemeProvider";

export function FarmIntelligenceGraphic() {
  const { theme, radius, shadows, spacing, typography } = useAppTheme();

  return (
    <View
      accessibilityLabel="Connected farm overview showing a healthy cow and live monitoring"
      accessibilityRole="image"
      style={[styles.frame, shadows.large, { borderRadius: radius.xxl, backgroundColor: theme.colors.surface }]}
    >
      <LinearGradient
        colors={theme.gradients.primary}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.sky, { borderTopLeftRadius: radius.xxl, borderTopRightRadius: radius.xxl }]}
      >
        <View style={styles.orbitOuter} />
        <View style={styles.orbitInner} />
        <View style={[styles.sun, { backgroundColor: theme.colors.accent }]} />
        <View style={styles.barn}>
          <View style={[styles.roof, { borderBottomColor: "#F7E9C3" }]} />
          <View style={styles.barnBody}>
            <View style={styles.barnDoor} />
          </View>
        </View>
        <View style={[styles.pastureBack, { backgroundColor: theme.colors.secondary }]} />
        <View style={[styles.pastureFront, { backgroundColor: theme.colors.primaryDark }]} />
      </LinearGradient>

      <View style={[styles.metricRow, { padding: spacing.lg, gap: spacing.sm }]}>
        <View style={[styles.animalBadge, { backgroundColor: theme.colors.surfaceSecondary, borderRadius: radius.lg }]}>
          <Text style={[styles.animalId, { color: theme.colors.primaryDark }]}>COW 024</Text>
          <Text style={[styles.animalStatus, { color: theme.colors.success }]}>● Healthy</Text>
        </View>
        <View style={styles.metricCopy}>
          <Text style={[styles.metricEyebrow, { color: theme.colors.textSecondary }]}>FARM INSIGHT</Text>
          <Text style={[styles.metricTitle, { color: theme.colors.text, fontSize: typography.sizes.subtitle }]}>Everything connected</Text>
          <View style={styles.signalRow}>
            {[0.35, 0.55, 0.78, 1].map((height, index) => (
              <View
                key={height}
                style={[styles.signalBar, { height: 18 * height, backgroundColor: index === 3 ? theme.colors.accent : theme.colors.primary }]}
              />
            ))}
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { width: "100%", maxWidth: 430, overflow: "hidden", alignSelf: "center" },
  sky: { height: 230, overflow: "hidden" },
  orbitOuter: { position: "absolute", width: 190, height: 190, borderRadius: 95, borderWidth: 1, borderColor: "rgba(255,255,255,0.28)", top: 18, right: 22 },
  orbitInner: { position: "absolute", width: 116, height: 116, borderRadius: 58, borderWidth: 1, borderColor: "rgba(255,255,255,0.34)", top: 55, right: 59 },
  sun: { position: "absolute", width: 14, height: 14, borderRadius: 7, top: 66, right: 43 },
  barn: { position: "absolute", left: "20%", bottom: 46, width: 112, alignItems: "center" },
  roof: { width: 0, height: 0, borderLeftWidth: 66, borderRightWidth: 66, borderBottomWidth: 58, borderLeftColor: "transparent", borderRightColor: "transparent" },
  barnBody: { width: 102, height: 72, backgroundColor: "#F9F3E4", alignItems: "center", justifyContent: "flex-end" },
  barnDoor: { width: 35, height: 44, backgroundColor: "#9A673E", borderTopLeftRadius: 16, borderTopRightRadius: 16 },
  pastureBack: { position: "absolute", left: -30, bottom: -65, width: "120%", height: 135, borderRadius: 100, opacity: 0.8 },
  pastureFront: { position: "absolute", right: -60, bottom: -100, width: "120%", height: 160, borderRadius: 120, opacity: 0.95 },
  metricRow: { minHeight: 104, flexDirection: "row", alignItems: "center" },
  animalBadge: { paddingHorizontal: 14, paddingVertical: 12, minWidth: 104 },
  animalId: { fontSize: 11, fontWeight: "800", letterSpacing: 0.6 },
  animalStatus: { fontSize: 12, fontWeight: "700", marginTop: 5 },
  metricCopy: { flex: 1, minWidth: 0 },
  metricEyebrow: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  metricTitle: { fontWeight: "700", marginTop: 2 },
  signalRow: { position: "absolute", right: 0, bottom: 2, flexDirection: "row", alignItems: "flex-end", gap: 3 },
  signalBar: { width: 5, borderRadius: 3 },
});
