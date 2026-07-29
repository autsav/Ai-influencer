import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f8f9fa",
          100: "#e9ecef",
          200: "#dee2e6",
          300: "#ced4da",
          400: "#adb5bd",
          500: "#6c757d",
          600: "#495057",
          700: "#343a40",
          800: "#212529",
          900: "#0d0f12",
        },
        // Claude-style warm palette for landing/lead surfaces.
        // Used by web/app/lead/* — dashboard brand-* untouched above.
        parchment: {
          DEFAULT: "#f5f4ed", // canvas
          ivory: "#faf9f5", // cards
          sand: "#e8e6dc", // footer band
          border: "#f0eee6", // warm 1px hairline
        },
        terracotta: {
          DEFAULT: "#c96442",
          deep: "#a4502f",
          soft: "#e08967",
        },
        ink: {
          DEFAULT: "#171717", // hero button bg
          soft: "#3a3a3a", // body text
          // 6.2:1 on parchment, 5.4:1 on sand — passes WCAG AA on both.
          muted: "#595959",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Crimson Pro", "Georgia", "serif"],
      },
      letterSpacing: {
        tightish: "-0.015em",
      },
      maxWidth: {
        prose: "68ch",
      },
    },
  },
  plugins: [],
};
export default config;