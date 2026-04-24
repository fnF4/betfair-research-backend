import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0e1013",
        panel: "#161a1f",
        "panel-2": "#1d2329",
        line: "#232a31",
        fg: "#e6e9ee",
        muted: "#8a93a0",
        accent: "#3ad29f",
        warn: "#ffb454",
        bad: "#ef5b5b",
        blue: "#60a5fa",
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
