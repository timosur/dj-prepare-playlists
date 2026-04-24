/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 900: '#0b0d10', 700: '#1a1d22', 500: '#2c3038' },
        crate: { 500: '#7c5cff', 600: '#6a48f0' },
      },
    },
  },
  plugins: [],
}
