/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Accretion design token palette
        bg:      '#0a0a0a',
        surface: '#171717',
        's2':    '#1e1e1e',
        's3':    '#262626',
        accent:  '#ff6207',
        'accent-hover': '#cc4e06',
        'accent-dim':   '#ffead2',
        // Override Tailwind orange to match Accretion exactly
        orange: {
          400: '#ff8432',
          500: '#ff6207',
          600: '#cc4e06',
        },
      },
      fontFamily: {
        sans:    ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Switzer', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
