/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-family)", "Verdana", "Tahoma", "sans-serif"],
      },
      colors: {
        ink: "var(--ink)",
        panel: "var(--panel)",
        brand: "var(--brand)",
        accent: "var(--accent)",
        gold: "var(--gold)",
      },
    },
  },
  plugins: [],
};
