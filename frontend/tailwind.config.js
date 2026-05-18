/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0a',
        surface: '#111111',
        card: '#161616',
        cardHover: '#1c1c1c',
        primary: {
          500: '#e63946',
          600: '#c1272d',
          400: '#ff4d5a',
        },
        text: {
          main: '#f0f0f0',
          muted: '#888888',
        },
        border: '#222222'
      },
      boxShadow: {
        'glow': '0 0 20px rgba(230, 57, 70, 0.25)',
        'glow-strong': '0 0 30px rgba(230, 57, 70, 0.4)',
      }
    },
  },
  plugins: [],
}
