import { useContext, useEffect, useRef } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { SafeAreaInsetsContext } from "react-native-safe-area-context";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";
import { AppButton } from "./AppButton";
import { FadeInView } from "./FadeInView";

export function ConfirmationDialog({
  visible,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  onConfirm,
  onCancel,
}) {
  const { theme, radius, spacing, typography, shadows } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const insets = useContext(SafeAreaInsetsContext) || { top: 0, right: 0, bottom: 0, left: 0 };
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!visible) return undefined;
    const timer = setTimeout(() => cancelRef.current?.focus?.(), reduceMotion ? 0 : 120);
    return () => clearTimeout(timer);
  }, [reduceMotion, visible]);

  return (
    <Modal
      visible={visible}
      transparent
      animationType={reduceMotion ? "none" : "fade"}
      onRequestClose={pending ? undefined : onCancel}
      statusBarTranslucent
    >
      <View style={[styles.overlay, { backgroundColor: theme.colors.overlay, paddingTop: Math.max(insets.top, spacing.lg), paddingBottom: Math.max(insets.bottom, spacing.lg), paddingHorizontal: spacing.lg }]}>
        <Pressable
          accessibilityLabel="Close confirmation dialog"
          disabled={pending}
          onPress={onCancel}
          style={StyleSheet.absoluteFillObject}
        />
        <FadeInView style={styles.dialogWrap} distance={reduceMotion ? 0 : 12}>
          <View
            accessibilityViewIsModal
            accessibilityRole="alert"
            accessibilityLabel={`${title}. ${message}`}
            style={[
              styles.dialog,
              shadows.large,
              {
                backgroundColor: theme.colors.surface,
                borderColor: theme.colors.border,
                borderRadius: radius.xl,
                padding: spacing.xxl,
              },
            ]}
          >
            <Text
              style={{
                color: theme.colors.text,
                fontSize: typography.sizes.title,
                lineHeight: typography.lineHeights.title,
                fontWeight: typography.weights.bold,
              }}
            >
              {title}
            </Text>
            <Text
              style={{
                color: theme.colors.textSecondary,
                fontSize: typography.sizes.body,
                lineHeight: typography.lineHeights.body,
                marginTop: spacing.sm,
              }}
            >
              {message}
            </Text>
            <View style={[styles.actions, { gap: spacing.md, marginTop: spacing.xxl }]}>
              <View style={styles.action}>
                <AppButton buttonRef={cancelRef} title={cancelLabel} variant="outline" onPress={onCancel} disabled={pending} />
              </View>
              <View style={styles.action}>
                <AppButton
                  title={confirmLabel}
                  variant={destructive ? "danger" : "primary"}
                  onPress={onConfirm}
                  loading={pending}
                />
              </View>
            </View>
          </View>
        </FadeInView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  dialogWrap: { width: "100%", maxWidth: 480 },
  dialog: { width: "100%", borderWidth: 1 },
  actions: { flexDirection: "row", flexWrap: "wrap" },
  action: { flex: 1, minWidth: 140 },
});
