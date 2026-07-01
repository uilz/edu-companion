/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Page backgrounds
        page: 'var(--color-page)',
        'page-secondary': 'var(--color-page-secondary)',
        // Surface (cards, panels)
        surface: 'var(--color-surface)',
        'surface-hover': 'var(--color-surface-hover)',
        'surface-elevated': 'var(--color-surface-elevated)',
        // Ink (text)
        'ink-primary': 'var(--color-ink-primary)',
        'ink-secondary': 'var(--color-ink-secondary)',
        'ink-muted': 'var(--color-ink-muted)',
        'ink-link': 'var(--color-ink-link)',
        // Accent
        accent: 'var(--color-accent)',
        'accent-hover': 'var(--color-accent-hover)',
        'accent-soft': 'var(--color-accent-soft)',
        // Status
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        danger: 'var(--color-danger)',
        info: 'var(--color-info)',
        // Divider
        divider: 'var(--color-divider)',
        'divider-hover': 'var(--color-divider-hover)',
        // Input
        input: 'var(--color-input)',
        'input-focus': 'var(--color-input-focus)',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
      fontSize: {
        'fine': ['0.75rem', { lineHeight: '1.3' }],
        'caption': ['0.875rem', { lineHeight: '1.4' }],
        'body': ['1rem', { lineHeight: '1.65' }],
        'subhead': ['1.0625rem', { lineHeight: '1.4', fontWeight: '500' }],
        'heading': ['1.25rem', { lineHeight: '1.35', fontWeight: '600' }],
        'title': ['1.5rem', { lineHeight: '1.3', fontWeight: '600' }],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px',
      },
      boxShadow: {
        sm: '0 1px 3px rgba(0,0,0,0.08)',
        md: '0 4px 16px rgba(0,0,0,0.10)',
        glow: '0 2px 12px rgba(59,130,246,0.15)',
      },
      spacing: {
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '24px',
        '6': '32px',
        '8': '48px',
      },
      transitionDuration: {
        fast: '100ms',
        normal: '150ms',
        slow: '300ms',
      },
    },
  },
  plugins: [],
};
