/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: '#0066FF',
        background: '#0a0a0a',
        surface: '#262626',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'sans-serif'],
        english: ['Inter', 'sans-serif'],
        chinese: ['Noto Sans SC', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
