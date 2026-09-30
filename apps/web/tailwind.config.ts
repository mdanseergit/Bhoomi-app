import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Base surfaces ───────────────────────────────────────── */
        background: "#F4F7F1",       /* warm off-white with green tint */
        surface: "#FFFFFF",
        "text-primary": "#1A2E12",   /* very dark green from logo */
        "text-secondary": "#4A5D42", /* muted dark green */
        "text-muted": "#7E8F77",     /* softer green-gray */
        border: "#D4DDD0",           /* light green border */
        "dark-surface": "#0F1A0B",   /* deep dark green */
        "dark-text": "#E8F0E4",      /* light green for dark mode */

        /* ── Primary palette (derived from logo) ─────────────────── */
        primary: {
          DEFAULT: "#4A7C2E",        /* core leaf green from logo */
          light: "#6FAE45",          /* bright green accent */
          deep: "#2D5A18",           /* dark green from logo icon */
          soft: "#E2EDDA",           /* very light green tint */
          "50": "#F0F7EC",
          "100": "#DFF0D5",
          "200": "#BFE1AB",
          "300": "#95CC74",
          "400": "#6FAE45",
          "500": "#4A7C2E",
          "600": "#3A6623",
          "700": "#2D5A18",
          "800": "#1E3A10",
          "900": "#142A0A",
        },

        /* ── Accent (earth / soil tones) ─────────────────────────── */
        accent: {
          DEFAULT: "#8B6914",
          soft: "#F5ECD4",
        },

        /* ── Semantic ────────────────────────────────────────────── */
        success: "#3D8B26",
        warning: "#A87B2A",
        danger: "#B34A3C",
      },
      fontFamily: {
        sans: [
          "Inter",
          "Noto Sans",
          "Noto Sans Devanagari",
          "Noto Sans Bengali",
          "Noto Sans Tamil",
          "Noto Sans Telugu",
          "Noto Sans Kannada",
          "Noto Sans Malayalam",
          "Noto Sans Gujarati",
          "Noto Sans Gurmukhi",
          "Noto Sans Oriya",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      fontSize: {
        "page-title": ["30px", { lineHeight: "1.25", fontWeight: "600" }],
        "section-title": ["20px", { lineHeight: "1.3", fontWeight: "600" }],
        "card-title": ["15px", { lineHeight: "1.4", fontWeight: "600" }],
        metric: ["32px", { lineHeight: "1.1", fontWeight: "700" }],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        subtle: "0 1px 2px rgba(26,46,18,0.04), 0 1px 8px rgba(26,46,18,0.03)",
        "card-hover": "0 4px 16px rgba(26,46,18,0.08), 0 1px 4px rgba(26,46,18,0.04)",
      },
      transitionDuration: {
        DEFAULT: "180ms",
      },
      keyframes: {
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.3s ease-out",
        shimmer: "shimmer 1.5s ease-in-out infinite",
        in: "fade-in-up 0.2s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
