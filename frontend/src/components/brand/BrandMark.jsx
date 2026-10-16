import { StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useAppTheme } from "../../theme/ThemeProvider";

export function BrandMark({ size = 72, showWordmark = false, inverse = false }) {
  const { theme, radius, typography } = useAppTheme();
  const markRadius = Math.max(radius.md, Math.round(size * 0.28));
  const foreground = inverse ? theme.colors.primaryDark : theme.colors.onPrimary;

  return (
    <View
      accessibilityLabel={showWordmark ? "ICMS, Intelligent Cattle Management System" : "ICMS"}
      accessibilityRole="image"
      style={styles.row}
    >
      <LinearGradient
        colors={inverse ? ["#F8FFF9", "#DDF5E9"] : theme.gradients.primary}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.mark, { width: size, height: size, borderRadius: markRadius }]}
      >
        <View style={[styles.horn, styles.leftHorn, { borderColor: foreground }]} />
        <View style={[styles.horn, styles.rightHorn, { borderColor: foreground }]} />
        <View style={[styles.face, { borderColor: foreground }]}>
          <View style={styles.eyes}>
            <View style={[styles.eye, { backgroundColor: foreground }]} />
            <View style={[styles.eye, { backgroundColor: foreground }]} />
          </View>
          <View style={[styles.muzzle, { borderColor: foreground }]} />
        </View>
        <View style={[styles.leaf, { backgroundColor: theme.colors.accent }]} />
      </LinearGradient>

      {showWordmark ? (
        <View style={styles.wordmark}>
          <Text style={[styles.icms, { color: theme.colors.text, fontSize: typography.sizes.title }]}>ICMS</Text>
          <Text style={[styles.name, { color: theme.colors.textSecondary }]}>Intelligent Cattle Management System</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  mark: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  horn: { position: "absolute", top: "24%", width: "30%", height: "18%", borderTopWidth: 3 },
  leftHorn: { left: "17%", borderLeftWidth: 3, borderTopLeftRadius: 20, transform: [{ rotate: "-12deg" }] },
  rightHorn: { right: "17%", borderRightWidth: 3, borderTopRightRadius: 20, transform: [{ rotate: "12deg" }] },
  face: { width: "45%", height: "48%", borderWidth: 3, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  eyes: { width: "60%", flexDirection: "row", justifyContent: "space-between", marginTop: "8%" },
  eye: { width: 4, height: 4, borderRadius: 2 },
  muzzle: { width: "58%", height: "25%", borderWidth: 2, borderRadius: 10, marginTop: "20%" },
  leaf: { position: "absolute", right: "15%", top: "13%", width: "16%", height: "25%", borderTopLeftRadius: 14, borderBottomRightRadius: 14, transform: [{ rotate: "18deg" }] },
  wordmark: { marginLeft: 12, flexShrink: 1 },
  icms: { fontWeight: "800", letterSpacing: 1 },
  name: { fontSize: 11, lineHeight: 15, marginTop: 1, maxWidth: 190 },
});
