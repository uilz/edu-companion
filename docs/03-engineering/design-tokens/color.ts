/**
 * AppleGo Design Tokens — Color (CSS Custom Properties)
 *
 * Extracted from Demo3.0 (preview.html)
 * All components should reference these CSS variables, never hardcode hex values.
 *
 * Usage in CSS:
 *   background: var(--color-surface);
 *   color: var(--color-ink-primary);
 *   box-shadow: 0 0 0 1px var(--color-divider-soft);
 */

export const colors = {
  // Page
  page: '#f5f5f7',
  pageSecondary: '#eeeef0',

  // Surface
  surface: '#ffffff',
  surfaceAlt: '#fafafa',
  surfaceHover: '#e8e8ec',

  // Ink (Text)
  inkPrimary: '#1c1c1e',
  inkSecondary: '#6c6c78',
  inkMuted: '#a0a0ab',
  inkLink: '#0a84ff',

  // Accent (Brand)
  accent: '#0a84ff',
  accentHover: '#0070e0',
  accentSoft: 'rgba(10,132,255,.08)',
  accentGlow: 'rgba(10,132,255,.12)',

  // Status
  success: '#34c759',
  successSoft: 'rgba(52,199,89,.12)',
  warning: '#ff9f0a',
  warningSoft: 'rgba(255,159,10,.12)',
  danger: '#ff3b30',
  dangerSoft: 'rgba(255,59,48,.10)',

  // Accent Variants (Tools)
  purple: '#af52de',
  purpleSoft: 'rgba(175,82,222,.10)',
  teal: '#5ac8fa',
  tealSoft: 'rgba(90,200,250,.12)',
  pink: '#ff2d92',
  pinkSoft: 'rgba(255,45,146,.10)',

  // Dividers
  divider: '#e5e5ea',
  dividerHover: '#d1d1d6',
  dividerSoft: '#f0f0f2',

  // Message Bubbles
  aiMsg: '#f7f3ea',
  aiMsgStrong: '#efe9d8',
  userMsg: '#ebe7dd',
} as const;

export type ColorToken = keyof typeof colors;
