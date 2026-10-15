import { useEffect, useRef, useState } from "react";
import { Animated, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";
import { getCardVariant } from "../../theme/variants";
import { FadeInView } from "./FadeInView";

export function AppCard({
  children,
  title,
  subtitle,
  overline,
  icon,
  action,
  variant = "default",
  onPress,
  accessibilityLabel,
  entranceDelay = 0,
  compact = false,
  style,
  testID,
}) {
  const { theme, shadows, radius, spacing, typography, animation } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const [focused, setFocused] = useState(false);
  const scale = useRef(new Animated.Value(1)).current;
  const interactive = typeof onPress === "function";
  const variantStyle = getCardVariant(theme, shadows, variant);

  useEffect(() => () => scale.stopAnimation(), [scale]);

  const animateScale = (value) => {
    Animated.timing(scale, {
      toValue: value,
      duration: reduceMotion ? 0 : animation.duration.fast,
      easing: animation.easing.standard,
      useNativeDriver: true,
    }).start();
  };

  const content = (
    <>
      {(icon || title || subtitle || overline || action) && (
        <View style={styles.header}>
          {icon ? (
            <View
              style={[
                styles.icon,
                { backgroundColor: theme.colors.surfaceSecondary, borderRadius: radius.md },
              ]}
              accessibilityElementsHidden
            >
              {typeof icon === "string" ? (
                <Text style={{ color: theme.colors.primary, fontWeight: typography.weights.bold }}>
                  {icon}
                </Text>
              ) : (
                icon
              )}
            </View>
          ) : null}
          <View style={styles.headingGroup}>
            {overline ? (
              <Text
                style={[
                  styles.overline,
                  {
                    color: theme.colors.primary,
                    fontSize: typography.sizes.caption,
                    letterSpacing: typography.letterSpacing.eyebrow,
                  },
                ]}
              >
                {overline}
              </Text>
            ) : null}
            {title ? (
              <Text
                style={{
                  color: theme.colors.text,
                  fontSize: typography.sizes.subtitle,
                  fontWeight: typography.weights.bold,
                  lineHeight: typography.lineHeights.subtitle,
                }}
              >
                {title}
              </Text>
            ) : null}
            {subtitle ? (
              <Text
                style={{
                  color: theme.colors.textSecondary,
                  fontSize: typography.sizes.small,
                  lineHeight: typography.lineHeights.small,
                  marginTop: spacing.xs,
                }}
              >
                {subtitle}
              </Text>
            ) : null}
          </View>
          {action ? <View style={{ marginLeft: spacing.md }}>{action}</View> : null}
        </View>
      )}
      {children ? <View style={(title || subtitle || overline || icon) && { marginTop: spacing.lg }}>{children}</View> : null}
    </>
  );

  const cardStyle = [
    styles.card,
    variantStyle,
    {
      borderRadius: radius.lg,
      padding: compact ? spacing.lg : spacing.xl,
      transform: [{ scale }],
    },
    focused && styles.focusBase,
    focused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: { borderColor: theme.colors.focusRing } }),
    style,
  ];

  return (
    <FadeInView delay={entranceDelay}>
      {interactive ? (
        <Animated.View style={{ transform: [{ scale }] }}>
          <Pressable
            testID={testID}
            accessibilityRole="button"
            accessibilityLabel={accessibilityLabel || title}
            onPress={onPress}
            onPressIn={() => animateScale(animation.scale.pressed)}
            onPressOut={() => animateScale(animation.scale.normal)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            style={[cardStyle, { transform: undefined }]}
          >
            {content}
          </Pressable>
        </Animated.View>
      ) : (
        <Animated.View testID={testID} style={cardStyle}>
          {content}
        </Animated.View>
      )}
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  card: { width: "100%" },
  header: { flexDirection: "row", alignItems: "center" },
  icon: { width: 44, height: 44, alignItems: "center", justifyContent: "center", marginRight: 12 },
  headingGroup: { flex: 1, minWidth: 0 },
  overline: { fontWeight: "700", marginBottom: 3 },
  focusBase: Platform.select({
    web: { outlineStyle: "solid", outlineWidth: 3, outlineOffset: 3 },
    default: { borderWidth: 2 },
  }),
});
