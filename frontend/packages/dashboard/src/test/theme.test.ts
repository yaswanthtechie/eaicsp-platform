import { describe, expect, it } from "vitest";
import { applyTokenTheme } from "../theme";
import { colors } from "../tokens";

describe("applyTokenTheme", () => {
  it("points shadcn colours at tokens.ts so cards are not white", () => {
    const root = document.createElement("div");

    applyTokenTheme(root);

    expect(root.style.getPropertyValue("--card")).toBe(colors.surface);
    expect(root.style.getPropertyValue("--card-foreground")).toBe(colors.text);
    expect(root.style.getPropertyValue("--muted-foreground")).toBe(colors.textMuted);
    expect(root.style.getPropertyValue("--destructive")).toBe(colors.danger);
  });
});