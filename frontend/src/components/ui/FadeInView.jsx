import { useEffect, useRef } from "react";
import { Animated } from "react-native";

import { useAppTheme } from "../../theme/ThemeProvider";
import { useAppReducedMotion } from "../../theme/useAppReducedMotion";

export function FadeInView({ children, delay = 0, distance = 10, style, ...props }) {
  const { animation } = useAppTheme();
  const reduceMotion = useAppReducedMotion();
  const opacity = useRef(new Animated.Value(reduceMotion ? 1 : 0)).current;
  const translateY = useRef(new Animated.Value(reduceMotion ? 0 : distance)).current;

  useEffect(() => {
    if (reduceMotion) {
      opacity.setValue(1);
      translateY.setValue(0);
      return undefined;
    }

    const entrance = Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: animation.duration.slow,
        delay,
        easing: animation.easing.standard,
        useNativeDriver: true,
      }),
      Animated.timing(translateY, {
        toValue: 0,
        duration: animation.duration.slow,
        delay,
        easing: animation.easing.standard,
        useNativeDriver: true,
      }),
    ]);

    entrance.start();
    return () => entrance.stop();
  }, [animation, delay, distance, opacity, reduceMotion, translateY]);

  return (
    <Animated.View style={[{ opacity, transform: [{ translateY }] }, style]} {...props}>
      {children}
    </Animated.View>
  );
}
