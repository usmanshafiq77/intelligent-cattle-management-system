import { themes } from "../src/theme/themes";
import { buttonSizes, getStatusVariant } from "../src/theme/variants";

function luminance(hex) {
  const channels = hex
    .replace("#", "")
    .match(/.{2}/g)
    .map((value) => Number.parseInt(value, 16) / 255)
    .map((value) => (value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return (0.2126 * channels[0]) + (0.7152 * channels[1]) + (0.0722 * channels[2]);
}

function contrast(foreground, background) {
  const light = Math.max(luminance(foreground), luminance(background));
  const dark = Math.min(luminance(foreground), luminance(background));
  return (light + 0.05) / (dark + 0.05);
}

describe("theme accessibility contract", () => {
  test.each(Object.entries(themes))("%s theme keeps primary text combinations readable", (_id, theme) => {
    expect(contrast(theme.colors.onPrimary, theme.colors.primary)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(theme.colors.text, theme.colors.background)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(theme.colors.textSecondary, theme.colors.background)).toBeGreaterThanOrEqual(4.5);
  });

  test.each(Object.entries(themes))("%s theme keeps status badges readable", (_id, theme) => {
    for (const status of ["active", "pending", "completed", "warning", "error"]) {
      const colors = getStatusVariant(theme, status);
      expect(contrast(colors.foreground, colors.background)).toBeGreaterThanOrEqual(4.5);
    }
  });

  test("every button size meets the minimum touch target", () => {
    for (const size of Object.values(buttonSizes)) {
      expect(size.minHeight).toBeGreaterThanOrEqual(44);
    }
  });
});
