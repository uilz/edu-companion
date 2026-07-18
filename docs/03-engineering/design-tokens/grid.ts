/**
 * AppleGo Design Tokens — Grid & Layout
 *
 * Extracted from Demo3.0 (preview.html)
 */

export const layout = {
  /** Max content width: 560px — centered single-column layout */
  contentMax: 560,
  /** Bottom navigation height: 68px (includes safe-area padding) */
  bottomNavHeight: 68,
  /** Top safe area for notch devices */
  safeAreaTop: 'env(safe-area-inset-top, 0)',
  /** Bottom safe area for home indicator */
  safeAreaBottom: 'env(safe-area-inset-bottom, 0)',
} as const;

export const breakpoint = {
  /** Mobile breakpoint: 480px — adjust padding, font sizes */
  mobile: 480,
} as const;

/**
 * Responsive rules (from Demo3.0):
 * - Default: max-width 560px centered, padding var(--space-4) on sides
 * - ≤480px: reduce padding to var(--space-3), shrink greeting/h1 sizes slightly
 * - Bottom nav: gap reduces at mobile, tabs compact
 */
export const responsiveRules = {
  default: {
    appPadding: 'var(--space-4)',
    appMaxWidth: '560px',
  },
  mobile: {
    appPadding: 'var(--space-3)',
    greetingSize: '26px',
    aiQuoteSize: '17px',
    finishQuoteSize: '19px',
  },
} as const;

export const grid = {
  /** More page: 2 columns with 12px gap */
  moreGrid: { columns: 2, gap: 12 },
  /** Today tools: horizontal flexbox with 10px gap, overflow-x auto */
  toolsRow: { gap: 10 },
  /** Practice options: single column, 10px gap */
  optionsColumn: { gap: 10 },
  /** Session stage dots: flex row, 4px gap */
  stageDots: { gap: 4 },
} as const;

export type LayoutToken = keyof typeof layout;
export type BreakpointToken = keyof typeof breakpoint;
export type GridToken = keyof typeof grid;
