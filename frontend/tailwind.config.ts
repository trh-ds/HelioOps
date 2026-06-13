import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        deep: { black: "#09090b", 900: "#18181b", 800: "#27272a", 700: "#3f3f46" },
        aurora: { DEFAULT: "#00FF9D", light: "#6EE7B7", dark: "#059669", glow: "#00FF9D22" },
        indigo: { DEFAULT: "#8B5CF6", light: "#A78BFA", dark: "#6D28D9" },
        warm: { DEFAULT: "#f59e0b", light: "#fbbf24", dark: "#d97706" },
        rose: { DEFAULT: "#ef4444", light: "#f87171" },
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "pulse-soft": "pulseSoft 3s ease-in-out infinite",
        "drift": "drift 30s linear infinite",
        "shine": "shine 2s ease-in-out infinite",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "0.8" },
        },
        drift: {
          "0%": { transform: "translateX(0) translateY(0)" },
          "50%": { transform: "translateX(20px) translateY(-10px)" },
          "100%": { transform: "translateX(0) translateY(0)" },
        },
        shine: {
          "0%": { backgroundPosition: "-200% center" },
          "100%": { backgroundPosition: "200% center" },
        },
      },
    },
  },
  plugins: [],
}

export default config
