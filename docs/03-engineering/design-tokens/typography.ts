/**
 * AppleGo Design Tokens — Typography
 *
 * Extracted from Demo3.0 (preview.html)
 * Always use these tokens. Never hardcode font sizes or families.
 */

export const fontFamily = {
  sans: "'Inter','Noto Sans SC',system-ui,-apple-system,sans-serif",
  serif: "'Noto Serif SC','Iowan Old Style',serif",
  mono: "'SF Mono','JetBrains Mono',monospace",
} as const;

export const fontSize = {
  /** 10.5px — Bottom nav labels */
  10: 10.5,
  /** 11px — Tags, badges */
  11: 11,
  /** 11.5px — Tool quick entry subtitles */
  115: 11.5,
  /** 12px — Secondary labels, meta, section titles */
  12: 12,
  /** 12.5px — Tool card descriptions */
  125: 12.5,
  /** 13px — Secondary text, links, tags */
  13: 13,
  /** 13.5px — Insight bubble text */
  135: 13.5,
  /** 14px — Secondary body, dates, descriptions */
  14: 14,
  /** 14.5px — File names, task text */
  145: 14.5,
  /** 15px — Body, buttons, preference rows */
  15: 15,
  /** 16px — Sub-headings, question text */
  16: 16,
  /** 17px — Growth narrative, profile mirror body */
  17: 17,
  /** 18px — Card titles */
  18: 18,
  /** 19px — AI quotes, reflection prompt */
  19: 19,
  /** 20px — Focus title */
  20: 20,
  /** 21px — Finish page AI quote */
  21: 21,
  /** 22px — Finish page title */
  22: 22,
  /** 26px — Welcome title, reader title */
  26: 26,
  /** 28px — Page titles */
  28: 28,
  /** 30px — Today greeting */
  30: 30,
  /** 40px — Pomodoro clock digits */
  40: 40,
  /** 48px — Large icon/emoji */
  48: 48,
  /** 56px — Welcome page apple icon */
  56: 56,
} as const;

export const fontWeight = {
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

export const lineHeight = {
  tight: 1.3,
  normal: 1.6,
  relaxed: 1.7,
  loose: 1.8,
  veryLoose: 1.9,
} as const;

export const letterSpacing = {
  tight: '-.02em',
  normal: 'normal',
  wide: '.05em',
  wider: '.08em',
} as const;

export type FontFamilyToken = keyof typeof fontFamily;
export type FontSizeToken = keyof typeof fontSize;
export type FontWeightToken = keyof typeof fontWeight;
export type LineHeightToken = keyof typeof lineHeight;
export type LetterSpacingToken = keyof typeof letterSpacing;
