import { useEffect, useRef, useState } from "react";
import { Animated, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";

export function AppInput({
  inputRef,
  label,
  placeholder,
  value,
  onChangeText,
  error,
  helperText,
  secureTextEntry = false,
  disabled = false,
  required = false,
  keyboardType = "default",
  autoCapitalize = "sentences",
  autoComplete,
  maxLength,
  multiline = false,
  accessibilityLabel,
  style,
  testID,
  ...props
}) {
  const { theme, radius, spacing, typography, animation, layout } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const [focused, setFocused] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [toggleFocused, setToggleFocused] = useState(false);
  const focusProgress = useRef(new Animated.Value(0)).current;
  const isPassword = secureTextEntry;
  const isSecure = isPassword && !passwordVisible;
  const message = error || helperText;

  useEffect(() => {
    if (!isPassword) setPasswordVisible(false);
  }, [isPassword]);

  const animateFocus = (toValue) => {
    Animated.timing(focusProgress, {
      toValue,
      duration: reduceMotion ? 0 : animation.duration.normal,
      easing: animation.easing.standard,
      useNativeDriver: false,
    }).start();
  };

  const borderColor = focusProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [error ? theme.colors.error : theme.colors.border, error ? theme.colors.error : theme.colors.focusRing],
  });

  return (
    <View style={[styles.wrapper, style]}>
      {label ? (
        <Text
          style={{
            color: theme.colors.text,
            fontSize: typography.sizes.small,
            lineHeight: typography.lineHeights.small,
            fontWeight: typography.weights.semibold,
            marginBottom: spacing.sm,
          }}
        >
          {label}
          {required ? <Text style={{ color: theme.colors.error }}> *</Text> : null}
        </Text>
      ) : null}
      <Animated.View
        style={[
          styles.inputContainer,
          {
            borderColor,
            borderRadius: radius.md,
            backgroundColor: disabled ? theme.colors.surfaceSecondary : theme.colors.surface,
            minHeight: multiline ? 112 : layout.inputHeight,
            opacity: disabled ? 0.68 : 1,
          },
          focused && Platform.select({ web: { boxShadow: `0 0 0 3px ${theme.colors.surfaceSecondary}` }, default: {} }),
        ]}
      >
        <TextInput
          ref={inputRef}
          testID={testID}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={theme.colors.textSecondary}
          editable={!disabled}
          secureTextEntry={isSecure}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoComplete={autoComplete}
          maxLength={maxLength}
          multiline={multiline}
          onFocus={() => {
            setFocused(true);
            animateFocus(1);
          }}
          onBlur={() => {
            setFocused(false);
            animateFocus(0);
          }}
          accessibilityLabel={accessibilityLabel || label || placeholder}
          accessibilityHint={message}
          accessibilityState={{ disabled }}
          accessibilityValue={error ? { text: `Invalid: ${error}` } : undefined}
          aria-invalid={Boolean(error)}
          style={[
            styles.input,
            {
              color: theme.colors.text,
              fontSize: typography.sizes.body,
              lineHeight: typography.lineHeights.body,
              textAlignVertical: multiline ? "top" : "center",
            },
            multiline && styles.multilineInput,
          ]}
          {...props}
        />
        {isPassword && !disabled ? (
          <Pressable
            testID={testID ? `${testID}-visibility` : undefined}
            onPress={() => setPasswordVisible((previous) => !previous)}
            onFocus={() => setToggleFocused(true)}
            onBlur={() => setToggleFocused(false)}
            accessibilityRole="button"
            accessibilityLabel={passwordVisible ? "Hide password" : "Show password"}
            accessibilityState={{ expanded: passwordVisible }}
            style={[
              styles.visibilityButton,
              { minHeight: layout.minTouchTarget, borderRadius: radius.sm },
              toggleFocused && styles.toggleFocusBase,
              toggleFocused && Platform.select({ web: { outlineColor: theme.colors.focusRing }, default: { borderColor: theme.colors.focusRing } }),
            ]}
          >
            <Text
              style={{
                color: theme.colors.primary,
                fontSize: typography.sizes.caption,
                fontWeight: typography.weights.bold,
              }}
            >
              {passwordVisible ? "Hide" : "Show"}
            </Text>
          </Pressable>
        ) : null}
      </Animated.View>
      {error ? (
        <Text
          accessibilityRole="alert"
          accessibilityLiveRegion="assertive"
          style={[styles.message, { color: theme.colors.error }]}
        >
          {error}
        </Text>
      ) : helperText ? (
        <Text accessibilityLiveRegion="polite" style={[styles.message, { color: theme.colors.textSecondary }]}>
          {helperText}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { width: "100%" },
  inputContainer: { flexDirection: "row", alignItems: "center", borderWidth: 1.5 },
  input: { flex: 1, minWidth: 0, paddingHorizontal: 16, paddingVertical: 13, outlineStyle: "none" },
  multilineInput: { minHeight: 110, paddingTop: 15 },
  visibilityButton: { justifyContent: "center", marginRight: 6, paddingHorizontal: 12 },
  visibilityText: { fontSize: 13, fontWeight: "700" },
  toggleFocusBase: Platform.select({
    web: { outlineStyle: "solid", outlineWidth: 3, outlineOffset: 1 },
    default: { borderWidth: 2 },
  }),
  message: { fontSize: 12, lineHeight: 18, marginTop: 6 },
});
