/**
 * AppleGo Design Tokens — Spacing
 *
 * Extracted from Demo3.0 (preview.html)
 * All spacing values in px. Use these tokens instead of hardcoded values.
 */

export const spacing = {
  /** 4px — Micro spacing, icon gaps */
  space1: 4,
  /** 8px — Small gaps, padding inside elements */
  space2: 8,
  /** 14px — Default spacing between sections */
  space3: 14,
  /** 18px — Card padding, section spacing */
  space4: 18,
  /** 28px — Large section spacing */
  space5: 28,
  /** 36px — Very large spacing */
  space6: 36,
  /** 56px — Hero section spacing */
  space8: 56,
} as const;

/**
 * Inline spacing values used in specific components
 * Only for cases where token-based spacing doesn't apply
 */
export const inlineSpacing = {
  /** 6px — Dot/icon/status indicator size */
  xxs: 6,
  /** 10px — Small gap within components */
  xs: 10,
  /** 12px — Grid gap, medium gap */
  sm: 12,
  /** 16px — Input padding, moderate gap */
  md: 16,
  /** 20px — Large button padding */
  lg: 20,
  /** 24px — Section/title bottom margin */
  xl: 24,
} as const;

export type SpacingToken = keyof typeof spacing;
export type InlineSpacingToken = keyof typeof inlineSpacing;
