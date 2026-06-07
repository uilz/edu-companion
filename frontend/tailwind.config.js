/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // ═══════════════════════════════════════════════════════
      // COLOR TOKENS — 语义层映射到 CSS 变量
      // ═══════════════════════════════════════════════════════
      colors: {
        // Page backgrounds
        page: 'var(--color-page)',
        'page-secondary': 'var(--color-page-secondary)',

        // Surface (cards, bubbles, panels)
        surface: 'var(--color-surface)',
        'surface-alt': 'var(--color-surface-alt)',
        'surface-hover': 'var(--color-surface-hover)',
        'surface-elevated': 'var(--color-surface-elevated)',

        // Ink (text)
        'ink-primary': 'var(--color-ink-primary)',
        'ink-secondary': 'var(--color-ink-secondary)',
        'ink-muted': 'var(--color-ink-muted)',
        'ink-on-dark': 'var(--color-ink-on-dark)',
        'ink-link': 'var(--color-ink-link)',

        // Accent
        accent: 'var(--color-accent)',
        'accent-soft': 'var(--color-accent-soft)',
        'accent-hover': 'var(--color-accent-hover)',
        'accent-glow': 'var(--color-accent-glow)',

        // Status
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        danger: 'var(--color-danger)',
        info: 'var(--color-info)',

        // Dividers
        divider: 'var(--color-divider)',
        'divider-soft': 'var(--color-divider-soft)',

        // Graph-specific
        'graph-node': 'var(--color-graph-node)',
        'graph-edge-active': 'var(--color-graph-edge-active)',
        'graph-edge-pending': 'var(--color-graph-edge-pending)',
        'graph-edge-suggested': 'var(--color-graph-edge-suggested)',
        'graph-node-mastered': 'var(--color-graph-node-mastered)',
        'graph-node-weak': 'var(--color-graph-node-weak)',

        // ── Backward-compatible aliases (old → new mapping) ──
        background: 'var(--color-page)',
        'bg-elevated': 'var(--color-page-secondary)',
        card: 'var(--color-surface)',
        'card-hover': 'var(--color-surface-hover)',
        text: 'var(--color-ink-primary)',
        'text-secondary': 'var(--color-ink-secondary)',
        'text-muted': 'var(--color-ink-muted)',
        'text-on-dark': 'var(--color-ink-on-dark)',
        border: 'var(--color-divider)',
        'border-hover': 'var(--color-divider-hover)',
        'border-soft': 'var(--color-divider-soft)',
        error: 'var(--color-danger)',
        input: 'var(--color-input)',
        'input-focus': 'var(--color-input-focus)',
        selection: 'var(--color-selection)',
      },

      // ═══════════════════════════════════════════════════════
      // FONT TOKENS
      // ═══════════════════════════════════════════════════════
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      fontSize: {
        // Semantic type scale
        hero: ['var(--text-hero-size)', { lineHeight: 'var(--text-hero-lineheight)', fontWeight: 'var(--text-hero-weight)', letterSpacing: 'var(--text-hero-tracking)' }],
        title: ['var(--text-title-size)', { lineHeight: 'var(--text-title-lineheight)', fontWeight: 'var(--text-title-weight)', letterSpacing: 'var(--text-title-tracking)' }],
        heading: ['var(--text-heading-size)', { lineHeight: 'var(--text-heading-lineheight)', fontWeight: 'var(--text-heading-weight)', letterSpacing: 'var(--text-heading-tracking)' }],
        subhead: ['var(--text-subhead-size)', { lineHeight: 'var(--text-subhead-lineheight)', fontWeight: 'var(--text-subhead-weight)', letterSpacing: 'var(--text-subhead-tracking)' }],
        body: ['var(--text-body-size)', { lineHeight: 'var(--text-body-lineheight)', fontWeight: 'var(--text-body-weight)', letterSpacing: 'var(--text-body-tracking)' }],
        'body-strong': ['var(--text-body-strong-size)', { lineHeight: 'var(--text-body-strong-lineheight)', fontWeight: 'var(--text-body-strong-weight)', letterSpacing: 'var(--text-body-strong-tracking)' }],
        caption: ['var(--text-caption-size)', { lineHeight: 'var(--text-caption-lineheight)', fontWeight: 'var(--text-caption-weight)', letterSpacing: 'var(--text-caption-tracking)' }],
        'caption-strong': ['var(--text-caption-strong-size)', { lineHeight: 'var(--text-caption-strong-lineheight)', fontWeight: 'var(--text-caption-strong-weight)', letterSpacing: 'var(--text-caption-strong-tracking)' }],
        fine: ['var(--text-fine-size)', { lineHeight: 'var(--text-fine-lineheight)', fontWeight: 'var(--text-fine-weight)', letterSpacing: 'var(--text-fine-tracking)' }],
        code: ['var(--text-code-size)', { lineHeight: 'var(--text-code-lineheight)', fontWeight: 'var(--text-code-weight)', letterSpacing: 'var(--text-code-tracking)' }],
      },

      // ═══════════════════════════════════════════════════════
      // SPACING TOKENS
      // ═══════════════════════════════════════════════════════
      spacing: {
        'space-1': 'var(--space-1)',
        'space-2': 'var(--space-2)',
        'space-3': 'var(--space-3)',
        'space-4': 'var(--space-4)',
        'space-5': 'var(--space-5)',
        'space-6': 'var(--space-6)',
        'space-8': 'var(--space-8)',
      },

      // ═══════════════════════════════════════════════════════
      // BORDER RADIUS TOKENS
      // ═══════════════════════════════════════════════════════
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        full: 'var(--radius-full)',
        card: 'var(--radius-md)',
        bubble: 'var(--radius-lg)',
      },

      // ═══════════════════════════════════════════════════════
      // BOX SHADOW TOKENS
      // ═══════════════════════════════════════════════════════
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        glow: 'var(--shadow-glow)',
      },

      // ═══════════════════════════════════════════════════════
      // MOTION TOKENS (transition-duration)
      // ═══════════════════════════════════════════════════════
      transitionDuration: {
        fast: 'var(--motion-fast)',
        normal: 'var(--motion-normal)',
        slow: 'var(--motion-slow)',
        slower: 'var(--motion-slower)',
      },
      transitionTimingFunction: {
        'ease-out': 'var(--ease-out)',
        'ease-in-out': 'var(--ease-in-out)',
        spring: 'var(--ease-spring)',
      },

      // ═══════════════════════════════════════════════════════
      // LAYOUT TOKENS
      // ═══════════════════════════════════════════════════════
      width: {
        sidebar: 'var(--sidebar-width)',
      },
      height: {
        'bottom-nav': 'var(--bottom-nav-height)',
      },
    },
  },
  plugins: [],
};
