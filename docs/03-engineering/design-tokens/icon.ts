/**
 * AppleGo Design Tokens — Icon System
 *
 * Extracted from Demo3.0 (preview.html)
 * All icons use inline SVG with 24x24 viewBox and 1.8px stroke by default.
 */

export const iconSize = {
  /** 18px — Inline icon, small button */
  sm: 18,
  /** 20px — Standard icon for nav, buttons */
  md: 20,
  /** 22px — Close/back chevron */
  lg: 22,
  /** 24px — Default icon size */
  xl: 24,
} as const;

/**
 * Icon palette for tool/function icons.
 * Each tool has a specific icon and background color.
 */
export const toolIcons = {
  flashcard: { icon: '🧠', bg: 'var(--color-purple-soft)' },
  reader: { icon: '📖', bg: 'var(--color-teal-soft)' },
  voice: { icon: '🗣️', bg: 'var(--color-pink-soft)' },
  canvas: { icon: '🧩', bg: 'var(--color-accent-soft)' },
  handwrite: { icon: '✏️', bg: 'var(--color-warning-soft)' },
  files: { icon: '📄', bg: 'var(--color-teal-soft)' },
  pomodoro: { icon: '⏱️', bg: 'var(--color-danger-soft)' },
  preferences: { icon: '⚙️', bg: 'var(--color-divider-soft)' },
} as const;

/**
 * Bottom nav SVG icons (inline SVG strings).
 * All use currentColor for stroke, 1.8px stroke-width.
 */
export const navIcons = {
  today: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  growth: `<svg viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8M14 7h7v7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  profile: `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.8"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  more: `<svg viewBox="0 0 24 24" fill="none"><circle cx="6" cy="12" r="2" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="2" stroke="currentColor" stroke-width="1.8"/><circle cx="18" cy="12" r="2" stroke="currentColor" stroke-width="1.8"/></svg>`,
} as const;

export type IconSizeToken = keyof typeof iconSize;
export type ToolIconToken = keyof typeof toolIcons;
export type NavIconToken = keyof typeof navIcons;
