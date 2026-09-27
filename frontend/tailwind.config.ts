import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Tajawal", "Cairo", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          DEFAULT: "#0f766e",
          dark: "#0d5952",
          light: "#14b8a6",
        },
        ink: "#0f172a",
        paper: "#fafafa",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
