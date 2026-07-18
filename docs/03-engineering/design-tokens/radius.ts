/**
 * AppleGo Design Tokens — Border Radius
 *
 * Extracted from Demo3.0 (preview.html)
 */

export const radius = {
  /** 8px — Small elements, tool icons */
  sm: 8,
  /** 14px — Cards, buttons, inputs, modals */
  md: 14,
  /** 18px — Large cards, major containers */
  lg: 18,
  /** 24px — Extra large, flashcard faces */
  xl: 24,
  /** 9999px — Fully rounded (pills, circles) */
  full: 9999,
} as const;

export type RadiusToken = keyof typeof radius;
