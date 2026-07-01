/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Page backgrounds
        page: '#0f1419',
        'page-secondary': '#161b22',
        // Surface (cards, panels)
        surface: '#1a2332',
        'surface-hover': '#212d3d',
        'surface-elevated': '#1e293b',
        // Ink (text)
        'ink-primary': '#e2e8f0',
        'ink-secondary': '#94a3b8',
        'ink-muted': '#64748b',
        'ink-link': '#60a5fa',
        // Accent
        accent: '#3b82f6',
        'accent-hover': '#2563eb',
        'accent-soft': 'rgba(59,130,246,0.12)',
        // Status
        success: '#4ade80',
        warning: '#fbbf24',
        danger: '#f87171',
        info: '#22d3ee',
        // Divider
        divider: '#1e293b',
        'divider-hover': '#334155',
        // Input
        input: '#0f172a',
        'input-focus': '#1a2332',
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
        sm: '0 1px 3px rgba(0,0,0,0.2)',
        md: '0 4px 16px rgba(0,0,0,0.3)',
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
