/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'll-deep': '#0B5D3B',
        'primary': '#087F5B',
        'dark-forest': '#063D2B',
        'mint': '#EAF6EF',
        'page-bg': '#F6F8F7',
        'card': '#FFFFFF',
        'text-main': '#172B23',
        'text-secondary': '#52665B',
        'border': '#DCE7DF',
        'warning': '#B7791F',
        'danger': '#C0392B',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
