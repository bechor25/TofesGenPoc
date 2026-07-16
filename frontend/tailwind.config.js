/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Heebo', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        accent: { DEFAULT: '#7c5cff', 600: '#6d4be0', 700: '#5b3fc4' },
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(15,23,42,.06)',
        cardDark: '0 1px 2px rgba(0,0,0,.3), 0 12px 32px rgba(0,0,0,.35)',
      },
    },
  },
  plugins: [],
}
