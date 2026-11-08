/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: { 50: "#f0f9f2", 100: "#dcf1e1", 200: "#bbe3c6", 300: "#8ecda2", 400: "#5bb07a", 500: "#36925a", 600: "#257546", 700: "#1d5d3a", 800: "#194a30", 900: "#153d29", 950: "#0a2216" },
        mint: { 50: "#f3fbf6", 100: "#e6f6ec" },
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.06)" },
    },
  },
  plugins: [],
};
