/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  // Koyu tema 'class' stratejisi: <html class="dark"> veya <html> arasinda toggle.
  // localStorage'da kullanici tercihi saklanir.
  darkMode: 'class',
  // BUG #061 fix (Kalite serüveni FE-002): dinamik interpolasyonla üretilen sınıflar
  // (`text-${color}-600`, `bg-${meta.color}-950/30`, `ring-${meta.color}-500` — Accounts.jsx,
  // RedLines.jsx) JIT tarafından prod build'de purge oluyordu (safelist yoktu). Palette
  // renkleri (brand/positive/negative/warn) literal geçmediği için üretilmezdi → görünmez renk.
  safelist: [
    { pattern: /(text|bg|ring|border)-(brand|positive|negative|warn)-(100|400|500|600|950)/, variants: ['dark'] },
    'bg-brand-950/30', 'bg-positive-950/30', 'bg-negative-950/30', 'bg-warn-950/30',
    'dark:bg-brand-950/30', 'dark:bg-positive-950/30', 'dark:bg-negative-950/30', 'dark:bg-warn-950/30',
  ],
  theme: {
    extend: {
      // FinancialOS palette — finansal arayuz icin disiplinli renkler
      colors: {
        // Brand
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
        },
        // Pozitif (yesil) — kar, tahsilat, taze fiyat
        positive: {
          50:  '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
          950: '#022c22',
        },
        // Negatif (kirmizi) — borc, kayip, kritik
        negative: {
          50:  '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
          950: '#450a0a',
        },
        // Uyari (amber) — bayatlik, dikkat
        warn: {
          50:  '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          950: '#451a03',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
};