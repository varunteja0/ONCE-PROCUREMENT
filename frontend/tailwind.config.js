/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx,html}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9eaff',
          200: '#bcd9ff',
          300: '#8ebfff',
          400: '#5a9cff',
          500: '#3478f6',
          600: '#225ad8',
          700: '#1c47ad',
          800: '#1a3c8a',
          900: '#19366f',
          950: '#0f1f44',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
