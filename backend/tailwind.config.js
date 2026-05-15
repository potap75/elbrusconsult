/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/src/**/*.{js,ts}",
    "../frontend/**/src/**/*.{ts,tsx,js,jsx}",
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
