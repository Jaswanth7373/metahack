/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Noto Sans", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5d9e2",
          300: "#b1b8c7",
          400: "#8791a7",
          500: "#67718a",
          600: "#515a71",
          700: "#42495c",
          800: "#2a2f3c",
          900: "#171a22",
          950: "#0e1016",
        },
        accent: {
          50: "#eef4ff",
          100: "#dae6ff",
          200: "#bdd3ff",
          300: "#90b6ff",
          400: "#5c8dfc",
          500: "#3767f6",
          600: "#2149eb",
          700: "#1a37d0",
          800: "#1c30a8",
          900: "#1d2f84",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)",
        lift: "0 8px 24px -8px rgba(16,24,40,0.18)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
        pulsering: {
          "0%": { boxShadow: "0 0 0 0 rgba(220,38,38,0.45)" },
          "100%": { boxShadow: "0 0 0 18px rgba(220,38,38,0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 220ms ease-out both",
        pulsering: "pulsering 1.4s ease-out infinite",
      },
    },
  },
  plugins: [],
};
