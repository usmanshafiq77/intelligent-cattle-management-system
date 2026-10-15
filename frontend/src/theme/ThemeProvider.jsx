import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { DEFAULT_THEME, isThemeId, themes } from "./themes";
import { animation, layout, radius, shadows, spacing, typography } from "./tokens";

export const THEME_STORAGE_KEY = "@icms/appearance/theme/v1";

const ThemeContext = createContext(null);

export function ThemeProvider({ children, persistPreference = true }) {
  const [themeId, setThemeId] = useState(DEFAULT_THEME);
  const [isThemeReady, setIsThemeReady] = useState(!persistPreference);
  const [themeRestoreError, setThemeRestoreError] = useState(false);
  const themeIdRef = useRef(DEFAULT_THEME);

  useEffect(() => {
    if (!persistPreference) return undefined;

    let active = true;

    async function restoreTheme() {
      try {
        const storedId = await AsyncStorage.getItem(THEME_STORAGE_KEY);

        if (active && isThemeId(storedId)) {
          themeIdRef.current = storedId;
          setThemeId(storedId);
        }
      } catch {
        if (active) setThemeRestoreError(true);
      } finally {
        if (active) setIsThemeReady(true);
      }
    }

    restoreTheme();
    return () => {
      active = false;
    };
  }, [persistPreference]);

  const changeTheme = useCallback(async (nextThemeId) => {
    if (!isThemeId(nextThemeId)) {
      throw new Error(`Unknown theme: ${nextThemeId}`);
    }

    const previousThemeId = themeIdRef.current;
    if (nextThemeId === previousThemeId) return;

    themeIdRef.current = nextThemeId;
    setThemeId(nextThemeId);

    if (!persistPreference) return;

    try {
      await AsyncStorage.setItem(THEME_STORAGE_KEY, nextThemeId);
    } catch (error) {
      themeIdRef.current = previousThemeId;
      setThemeId(previousThemeId);
      throw error;
    }
  }, [persistPreference]);

  const value = useMemo(
    () => ({
      themeId,
      theme: themes[themeId],
      themes,
      changeTheme,
      isThemeReady,
      themeRestoreError,
      spacing,
      radius,
      typography,
      animation,
      shadows,
      layout,
    }),
    [changeTheme, isThemeReady, themeId, themeRestoreError],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useAppTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useAppTheme must be used inside ThemeProvider");
  }

  return context;
}
