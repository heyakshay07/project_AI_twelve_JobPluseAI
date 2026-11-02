/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Instrument Sans"', "system-ui", "Segoe UI", "sans-serif"] },
      colors: {
        ink: "#0e1b2c",
        paper: "#eef2f4",
        line: "#d5dde2",
        accent: { DEFAULT: "#0f5c6e", dark: "#0a4452" },
      },
    },
  },
  plugins: [],
};
