import { colors } from "./tokens";

// shadcn/ui components read their colours from CSS variables. Its defaults
// are a LIGHT theme, which renders white cards on our dark dashboard.
// Point every variable at tokens.ts so tokens stay the single source.
const themeVariables: Record<string, string> = {
  "--background": colors.bg,
  "--foreground": colors.text,
  "--card": colors.surface,
  "--card-foreground": colors.text,
  "--popover": colors.surface,
  "--popover-foreground": colors.text,
  "--primary": colors.primary,
  "--primary-foreground": colors.text,
  "--secondary": colors.border,
  "--secondary-foreground": colors.text,
  "--muted": colors.border,
  "--muted-foreground": colors.textMuted,
  "--accent": colors.border,
  "--accent-foreground": colors.text,
  "--destructive": colors.danger,
  "--border": colors.border,
  "--input": colors.border,
  "--ring": colors.primary,
};

export function applyTokenTheme(
  root: HTMLElement = document.documentElement,
): void {
  Object.entries(themeVariables).forEach(([name, value]) => {
    root.style.setProperty(name, value);
  });
}