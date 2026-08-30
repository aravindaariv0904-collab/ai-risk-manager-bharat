/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // Semantic risk colors
        risk: {
          low: 'hsl(var(--risk-low))',
          'low-bg': 'hsl(var(--risk-low-bg))',
          medium: 'hsl(var(--risk-medium))',
          'medium-bg': 'hsl(var(--risk-medium-bg))',
          high: 'hsl(var(--risk-high))',
          'high-bg': 'hsl(var(--risk-high-bg))',
        },
        // Extended semantic palette
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        // India flag inspired accents
        saffron: {
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
        },
        india: {
          green: '#138808',
          saffron: '#FF9933',
          navy: '#000080',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        'glass': '0 8px 32px rgba(31, 38, 135, 0.08)',
        'card-hover': '0 8px 24px rgba(0, 0, 0, 0.1)',
        'primary-glow': '0 8px 24px rgba(99, 102, 241, 0.3)',
        'risk-high': '0 4px 14px rgba(239, 68, 68, 0.25)',
        'risk-medium': '0 4px 14px rgba(245, 158, 11, 0.25)',
        'risk-low': '0 4px 14px rgba(16, 185, 129, 0.25)',
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease both',
        'fade-in-up': 'fade-in-up 0.4s ease both',
        'slide-in-right': 'slide-in-right 0.3s ease both',
        'pulse-ring': 'pulse-ring 2s infinite',
        'shimmer': 'shimmer 1.5s infinite',
        'risk-fill': 'risk-fill 1s ease-out both',
        'bounce-subtle': 'bounce-subtle 0.6s ease',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'bounce-subtle': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.05)' },
        },
      },
      backdropBlur: {
        xs: '4px',
      },
    },
  },
  plugins: [],
}