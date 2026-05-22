/** @type {import('tailwindcss').Config} */
export default {
  content: ["./app/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0f766e",
          dark: "#134e4a",
          light: "#5eead4",
        },
      },
    },
  },
  plugins: [],
};
