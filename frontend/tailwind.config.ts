import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#1a1512",
          900: "#211a15",
          800: "#2b221b",
          700: "#3a2f26",
          600: "#4d4033",
          500: "#6b5c48",
          400: "#8f7d64",
          300: "#b3a48c",
          200: "#d9cdb8",
          100: "#f5ecdd",
        },
        signal: {
          DEFAULT: "#e0904a",
          dim: "#c07536",
          bright: "#f4bb80",
        },
        flag: {
          DEFAULT: "#f2c94c",
        },
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(224, 144, 74, 0.15), 0 0 24px -8px rgba(224, 144, 74, 0.35)",
      },
      keyframes: {
        pulseDot: {
          "0%, 80%, 100%": { opacity: "0.25", transform: "scale(0.85)" },
          "40%": { opacity: "1", transform: "scale(1)" },
        },
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-dot": "pulseDot 1.2s infinite ease-in-out",
        rise: "rise 0.25s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;