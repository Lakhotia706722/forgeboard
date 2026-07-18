import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ForgeBoard brand palette
        forge: {
          50:  '#f0f4ff',
          100: '#dce6ff',
          200: '#b8ccff',
          300: '#85a8ff',
          400: '#4d7dff',
          500: '#1a54ff',
          600: '#0038e6',
          700: '#002bb8',
          800: '#001f8a',
          900: '#001566',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
