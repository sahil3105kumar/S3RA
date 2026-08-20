import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a0d12",
          900: "#10141b",
          800: "#161b24",
          700: "#1f2530",
          600: "#2a3140",
          500: "#3a4356",
          400: "#5b6577",
          300: "#8891a1",
          200: "#b7bdc8",
          100: "#e4e7ec",
        },
        signal: {
          DEFAULT: "#5eead4",
          dim: "#2dd4bf",
          bright: "#99f6e4",
        },
        flag: {
          DEFAULT: "#f0b429",
        },
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(94, 234, 212, 0.15), 0 0 24px -8px rgba(94, 234, 212, 0.35)",
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
