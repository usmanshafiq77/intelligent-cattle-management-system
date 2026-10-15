import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";

export function Skeleton({ lines = 3, style }) {
  const { theme, radius, spacing, animation } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const opacity = useRef(new Animated.Value(0.48)).current;

  useEffect(() => {
    if (reduceMotion) return undefined;

    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.82, duration: animation.duration.slow, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.48, duration: animation.duration.slow, useNativeDriver: true }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [animation, opacity, reduceMotion]);

  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.container, { gap: spacing.sm }, style]}
    >
      {Array.from({ length: lines }, (_, index) => (
        <Animated.View
          key={index}
          style={{
            width: index === lines - 1 ? "62%" : "100%",
            height: index === 0 ? 18 : 14,
            borderRadius: radius.sm,
            backgroundColor: theme.colors.skeleton,
            opacity,
          }}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({ container: { width: "100%" } });
