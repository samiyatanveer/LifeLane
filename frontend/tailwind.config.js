/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'll-g': 'var(--g)',
        'll-g2': 'var(--g2)',
        'll-gold': 'var(--gold)',
        'll-tint': 'var(--tint)',
        'll-bg': 'var(--bg)',
        'll-surface': 'var(--surface)',
        'll-ink': 'var(--ink)',
        'll-mute': 'var(--mute)',
        'll-line': 'var(--line)',
        'll-red': 'var(--red)',
        'll-amber': 'var(--amber)',
        'll-road': 'var(--road)',
      },
      fontFamily: {
        heading: ['"Bricolage Grotesque"', 'sans-serif'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
