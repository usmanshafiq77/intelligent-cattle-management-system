import { Easing, Platform } from "react-native";

export const spacing = Object.freeze({
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  huge: 40,
  section: 48,
});

export const radius = Object.freeze({
  xs: 6,
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
  xxl: 30,
  pill: 999,
});

export const typography = Object.freeze({
  sizes: {
    caption: 12,
    small: 14,
    body: 16,
    subtitle: 18,
    title: 22,
    heading: 28,
    display: 34,
  },
  weights: {
    regular: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
    extrabold: "800",
  },
  lineHeights: {
    caption: 16,
    small: 20,
    body: 24,
    subtitle: 26,
    title: 30,
    heading: 36,
    display: 42,
  },
  letterSpacing: {
    label: 0.2,
    eyebrow: 1.2,
  },
});

export const animation = Object.freeze({
  duration: {
    instant: 0,
    fast: 140,
    normal: 240,
    slow: 380,
  },
  scale: {
    pressed: 0.975,
    normal: 1,
  },
  easing: {
    standard: Easing.out(Easing.cubic),
    emphasized: Easing.inOut(Easing.cubic),
  },
  spring: {
    damping: 18,
    stiffness: 220,
    mass: 0.8,
  },
});

export const shadows = Object.freeze({
  small: Platform.select({
    web: { boxShadow: "0 3px 12px rgba(15, 35, 30, 0.07)" },
    default: {
      elevation: 2,
      shadowColor: "#102C25",
      shadowOpacity: 0.08,
      shadowRadius: 5,
      shadowOffset: { width: 0, height: 2 },
    },
  }),
  medium: Platform.select({
    web: { boxShadow: "0 8px 24px rgba(15, 35, 30, 0.10)" },
    default: {
      elevation: 4,
      shadowColor: "#102C25",
      shadowOpacity: 0.12,
      shadowRadius: 12,
      shadowOffset: { width: 0, height: 5 },
    },
  }),
  large: Platform.select({
    web: { boxShadow: "0 16px 42px rgba(15, 35, 30, 0.14)" },
    default: {
      elevation: 7,
      shadowColor: "#102C25",
      shadowOpacity: 0.16,
      shadowRadius: 20,
      shadowOffset: { width: 0, height: 10 },
    },
  }),
});

export const layout = Object.freeze({
  screenPadding: 20,
  compactScreenPadding: 16,
  contentMaxWidth: 1120,
  formMaxWidth: 600,
  buttonHeight: 52,
  inputHeight: 54,
  minTouchTarget: 44,
  breakpoints: {
    compact: 420,
    tablet: 768,
    desktop: 1024,
  },
});
