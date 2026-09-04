/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aviation: {
          bg: '#070a12',
          surface: '#0f172a',
          card: '#151f38',
          panel: '#1a2644',
          border: '#243356',
          accent: '#2563eb',
          cyan: '#06b6d4',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#ef4444',
        }
      }
    },
  },
  plugins: [],
}
