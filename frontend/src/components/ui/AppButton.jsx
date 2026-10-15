import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Animated, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useAppTheme } from "../../theme/ThemeProvider";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";
import { buttonSizes, getButtonVariant } from "../../theme/variants";

const VALID_VARIANTS = new Set(["primary", "secondary", "outline", "danger"]);
const VALID_SIZES = new Set(["small", "medium", "large"]);

export function AppButton({
  title,
  onPress,
  variant = "primary",
  size = "medium",
  loading = false,
  disabled = false,
  fullWidth = true,
  leading,
  accessibilityLabel,
  accessibilityHint,
  buttonRef,
  style,
  testID,
}) {
  const { theme, radius, typography, animation } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;
  const [focused, setFocused] = useState(false);
  const inactive = disabled || loading;
  const safeVariant = VALID_VARIANTS.has(variant) ? variant : "primary";
  const safeSize = VALID_SIZES.has(size) ? size : "medium";
  const sizeStyle = buttonSizes[safeSize];
  const variantStyle = getButtonVariant(theme, safeVariant);

  useEffect(() => {
    if (inactive) scale.setValue(1);
    return () => scale.stopAnimation();
  }, [inactive, scale]);

  const animateTo = (value) => {
    Animated.timing(scale, {
      toValue: value,
      duration: reduceMotion ? 0 : animation.duration.fast,
      easing: animation.easing.standard,
      useNativeDriver: true,
    }).start();
  };

  return (
    <Animated.View
      style={[
        { transform: [{ scale }] },
        fullWidth ? styles.fullWidth : styles.fitContent,
        style,
      ]}
    >
      <Pressable
        ref={buttonRef}
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel || `${title}${loading ? ", loading" : ""}`}
        accessibilityHint={accessibilityHint}
        accessibilityState={{ disabled: inactive, busy: loading }}
        disabled={inactive}
        onPress={onPress}
        onPressIn={() => animateTo(animation.scale.pressed)}
        onPressOut={() => animateTo(animation.scale.normal)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[
          styles.button,
          {
            minHeight: sizeStyle.minHeight,
            paddingHorizontal: sizeStyle.paddingHorizontal,
            borderRadius: radius.md,
            opacity: inactive ? 0.58 : 1,
            borderWidth: safeVariant === "outline" ? 1.5 : 0,
            borderColor: variantStyle.border,
            backgroundColor: variantStyle.background,
          },
          focused && styles.focusBase,
          focused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: { borderColor: theme.colors.focusRing, borderWidth: 2 } }),
        ]}
      >
        {variantStyle.gradient ? (
          <LinearGradient
            colors={variantStyle.gradient}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={[StyleSheet.absoluteFillObject, { borderRadius: radius.md }]}
            pointerEvents="none"
          />
        ) : null}
        <View style={styles.content}>
          {loading ? <ActivityIndicator color={variantStyle.foreground} /> : leading || null}
          {!loading ? (
            <Text
              style={{
                color: variantStyle.foreground,
                fontSize: typography.sizes[sizeStyle.fontSize],
                fontWeight: typography.weights.bold,
                lineHeight: typography.lineHeights[sizeStyle.fontSize],
                textAlign: "center",
              }}
            >
              {title}
            </Text>
          ) : null}
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  fullWidth: { width: "100%" },
  fitContent: { alignSelf: "flex-start" },
  button: { overflow: "hidden", justifyContent: "center", alignItems: "center" },
  content: { minHeight: 24, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9, paddingVertical: 8 },
  focusBase: Platform.select({
    web: { outlineStyle: "solid", outlineWidth: 3, outlineOffset: 3 },
    default: {},
  }),
});
