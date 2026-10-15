import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("design system keeps shared values in theme modules", async () => {
  const tokenSource = await readFile(path.join(projectRoot, "src/theme/tokens.js"), "utf8");
  const themeSource = await readFile(path.join(projectRoot, "src/theme/themes.js"), "utf8");
  const variantSource = await readFile(path.join(projectRoot, "src/theme/variants.js"), "utf8");

  for (const token of ["spacing", "radius", "typography", "animation", "shadows", "layout"]) {
    assert.match(tokenSource, new RegExp(`export const ${token}`));
  }
  for (const themeId of ["emerald", "midnight", "indigo"]) {
    assert.match(themeSource, new RegExp(`${themeId}:`));
  }
  for (const helper of ["getButtonVariant", "getCardVariant", "getStatusVariant"]) {
    assert.match(variantSource, new RegExp(`export function ${helper}`));
  }
});

test("feedback, card, motion, and accessibility primitives are present", async () => {
  const required = [
    "src/components/ui/AppCard.jsx",
    "src/components/ui/StatCard.jsx",
    "src/components/ui/StatusBadge.jsx",
    "src/components/ui/FeedbackState.jsx",
    "src/components/ui/InlineFeedback.jsx",
    "src/components/ui/Skeleton.jsx",
    "src/components/ui/ConfirmationDialog.jsx",
    "src/components/ui/FadeInView.jsx",
    "src/theme/useAppReducedMotion.js",
  ];

  for (const relativePath of required) {
    const contents = await readFile(path.join(projectRoot, relativePath), "utf8");
    assert.ok(contents.length > 0, `${relativePath} must not be empty`);
  }
});
