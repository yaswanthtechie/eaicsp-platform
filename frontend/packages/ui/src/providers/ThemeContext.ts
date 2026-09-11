import { createContext } from "react";

export type Theme = "light" | "dark" | "high-contrast";

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<
  ThemeContextValue | undefined
>(undefined);