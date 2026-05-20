/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/src/**/*.{js,ts}",
    // Scan the React island sources, but skip nested node_modules to avoid
    // accidentally walking a multi-megabyte tree.
    "../frontend/*/src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Mountain / steel palette - "Elbrus" inspired.
        summit: {
          50:  "#eef5fb",
          100: "#d6e6f5",
          200: "#aecde9",
          300: "#7faddc",
          400: "#4f8acb",
          500: "#2d6ab7",
          600: "#0f4d8c",
          700: "#0d3f72",
          800: "#0a2f56",
          900: "#071f3a",
          950: "#04132b",
        },
        glacier: {
          50:  "#f5fafc",
          100: "#e3f1f7",
          200: "#c4e2ef",
          300: "#99cce3",
          400: "#5fafd1",
          500: "#3491b9",
          600: "#23739a",
          700: "#1f5d7c",
          800: "#1d4d65",
          900: "#193e51",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        // Display face for landing-page headlines and section titles. We
        // pair Sora (a geometric sans with a slight technical/futuristic
        // character) with Inter for body copy. Falls back to the same
        // system stack as `sans` so a font-load failure still looks fine.
        display: [
          "Sora",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      boxShadow: {
        // Used on the gradient icon tile on the home-page service cards.
        // Two-stop shadow: a soft summit-blue drop + an inset highlight
        // along the top edge so the tile reads as slightly raised glass.
        "tile-glow":
          "0 8px 24px -8px rgba(15, 77, 140, 0.55), inset 0 1px 0 rgba(255,255,255,0.18)",
      },
      keyframes: {
        // Card / section "reveal on scroll" animation. The vanilla-JS
        // IntersectionObserver in static/src/app.js toggles
        // `[data-reveal].is-visible`, which switches the animation on.
        reveal: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Subtle pulsing glow used by the icon tiles on hover/focus.
        glow: {
          "0%, 100%": {
            "box-shadow":
              "0 8px 24px -8px rgba(15, 77, 140, 0.45), inset 0 1px 0 rgba(255,255,255,0.18)",
          },
          "50%": {
            "box-shadow":
              "0 12px 32px -8px rgba(45, 106, 183, 0.65), inset 0 1px 0 rgba(255,255,255,0.28)",
          },
        },
      },
      animation: {
        reveal: "reveal 600ms cubic-bezier(0.16, 1, 0.3, 1) both",
        glow: "glow 2.8s ease-in-out infinite",
      },
      typography: ({ theme }) => ({
        slate: {
          css: {
            "--tw-prose-links": theme("colors.summit.700"),
            "--tw-prose-headings": theme("colors.slate.900"),
            "--tw-prose-quotes": theme("colors.slate.700"),
            "--tw-prose-quote-borders": theme("colors.summit.500"),
          },
        },
      }),
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
  ],
};
