const sharedSemanticColors = {
  success: "#167451",
  successSurface: "#E2F4EC",
  warning: "#9A5D0A",
  warningSurface: "#FFF1D6",
  error: "#B62F42",
  errorSurface: "#FBE7EA",
  info: "#245F9D",
  infoSurface: "#E5F0FC",
  onStatus: "#FFFFFF",
};

export const themes = Object.freeze({
  emerald: {
    id: "emerald",
    name: "Emerald Luxury",
    colors: {
      primary: "#087F65",
      primaryDark: "#075C4B",
      secondary: "#1AB69D",
      accent: "#D5A64B",
      background: "#F3F8F6",
      surface: "#FFFFFF",
      surfaceSecondary: "#E8F4EF",
      surfaceElevated: "#FFFFFF",
      text: "#142D27",
      textSecondary: "#586E66",
      border: "#D3E3DC",
      focusRing: "#087F65",
      overlay: "rgba(8, 37, 29, 0.58)",
      skeleton: "#D8E9E2",
      onPrimary: "#FFFFFF",
      onAccent: "#322406",
      ...sharedSemanticColors,
    },
    gradients: {
      primary: ["#075C4B", "#087F65", "#1AB69D"],
      background: ["#F3F8F6", "#E8F4EF"],
      highlight: ["#E2F4EC", "#F8FCFA"],
    },
  },
  midnight: {
    id: "midnight",
    name: "Midnight Teal",
    colors: {
      primary: "#102C46",
      primaryDark: "#0A1D30",
      secondary: "#168D96",
      accent: "#49BCA9",
      background: "#F1F6F9",
      surface: "#FFFFFF",
      surfaceSecondary: "#E5F0F4",
      surfaceElevated: "#FFFFFF",
      text: "#172D40",
      textSecondary: "#5D7384",
      border: "#D0E0E8",
      focusRing: "#168D96",
      overlay: "rgba(6, 24, 39, 0.62)",
      skeleton: "#D5E5EB",
      onPrimary: "#FFFFFF",
      onAccent: "#092F30",
      ...sharedSemanticColors,
    },
    gradients: {
      primary: ["#102C46", "#126274", "#168D96"],
      background: ["#F1F6F9", "#E5F0F4"],
      highlight: ["#DFF2F3", "#F8FBFC"],
    },
  },
  indigo: {
    id: "indigo",
    name: "Royal Indigo",
    colors: {
      primary: "#4D43A4",
      primaryDark: "#342B7A",
      secondary: "#7866C8",
      accent: "#A895E4",
      background: "#F7F5FD",
      surface: "#FFFFFF",
      surfaceSecondary: "#EEEAFB",
      surfaceElevated: "#FFFFFF",
      text: "#292346",
      textSecondary: "#68617F",
      border: "#DED7EF",
      focusRing: "#5B50B5",
      overlay: "rgba(31, 24, 67, 0.6)",
      skeleton: "#E2DCF2",
      onPrimary: "#FFFFFF",
      onAccent: "#241C4E",
      ...sharedSemanticColors,
    },
    gradients: {
      primary: ["#342B7A", "#4D43A4", "#7866C8"],
      background: ["#F7F5FD", "#EEEAFB"],
      highlight: ["#ECE7FA", "#FBFAFE"],
    },
  },
});

export const THEME_IDS = Object.freeze(Object.keys(themes));
export const DEFAULT_THEME = "emerald";

export function isThemeId(value) {
  return typeof value === "string" && Object.hasOwn(themes, value);
}
