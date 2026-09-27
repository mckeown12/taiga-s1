// Validated default palette (dataviz reference instance): light / dark steps.
export type Theme = {
  surface: string; card: string; ink: string; ink2: string; ink3: string; grid: string; band: string;
  s1: string; s2: string; wash1: string;
};
export const themes: Record<"light" | "dark", Theme> = {
  light: {surface: "#f4f3f0", card: "#fcfcfb", ink: "#0b0b0b", ink2: "#52514e", ink3: "#8a8984", grid: "#e6e5e1",
    band: "#efeeea", s1: "#2a78d6", s2: "#eb6834", wash1: "rgba(42,120,214,0.10)"},
  dark: {surface: "#121211", card: "#1a1a19", ink: "#ffffff", ink2: "#c3c2b7", ink3: "#8f8e86", grid: "#2e2e2b",
    band: "#222220", s1: "#3987e5", s2: "#d95926", wash1: "rgba(57,135,229,0.12)"},
};
