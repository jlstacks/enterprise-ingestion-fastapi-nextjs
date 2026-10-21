import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#071019',
        panel: '#0d1a27',
        cyan: '#39d0f2',
        mint: '#5ee4b2',
      },
      boxShadow: {
        panel: '0 24px 70px rgba(0, 0, 0, 0.22)',
      },
    },
  },
  plugins: [],
};

export default config;
