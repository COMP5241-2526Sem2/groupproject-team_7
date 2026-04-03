/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        sync: {
          nav: '#6B1E1E',
          'nav-deep': '#4a1414',
          cream: '#F5EFE3',
          parchment: '#EDE4D6',
          paper: '#FFFBF7',
          ink: '#292524',
        },
      },
      boxShadow: {
        glass: '0 8px 32px 0 rgba(92, 33, 33, 0.12)',
      },
      backdropBlur: {
        sync: '25px',
      },
      borderRadius: {
        card: '20px',
        inner: '12px',
        control: '8px',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Microsoft YaHei',
          'Noto Sans CJK SC',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
