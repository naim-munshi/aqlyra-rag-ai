"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

type ThemeProviderProps = {
  children: React.ReactNode;
};

export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="data-theme"
      defaultTheme="dark"
      enableSystem
      enableColorScheme
      storageKey="aqlyra-theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}