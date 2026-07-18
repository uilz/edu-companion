/**
 * AppleGo Design Tokens — Theme
 *
 * Extracted from Demo3.0 (preview.html)
 * Demo3.0 defines a single light theme. Dark theme is a future extension.
 * All theme values reference the semantic color tokens.
 */

export interface ThemeTokens {
  colors: {
    page: string;
    pageSecondary: string;
    surface: string;
    surfaceAlt: string;
    surfaceHover: string;
    inkPrimary: string;
    inkSecondary: string;
    inkMuted: string;
    inkLink: string;
    accent: string;
    accentHover: string;
    accentSoft: string;
    accentGlow: string;
    success: string;
    successSoft: string;
    warning: string;
    warningSoft: string;
    danger: string;
    dangerSoft: string;
    purple: string;
    purpleSoft: string;
    teal: string;
    tealSoft: string;
    pink: string;
    pinkSoft: string;
    divider: string;
    dividerHover: string;
    dividerSoft: string;
    aiMsg: string;
    aiMsgStrong: string;
    userMsg: string;
  };
  radius: {
    sm: number;
    md: number;
    lg: number;
    xl: number;
    full: number;
  };
  spacing: {
    space1: number;
    space2: number;
    space3: number;
    space4: number;
    space5: number;
    space6: number;
    space8: number;
  };
  fontFamily: {
    sans: string;
    serif: string;
    mono: string;
  };
  easing: {
    easeOut: string;
    easeSpring: string;
  };
}

/**
 * Light theme (Demo3.0 default).
 * All values match the CSS custom properties in preview.html.
 */
export const lightTheme: ThemeTokens = {
  colors: {
    page: '#f5f5f7',
    pageSecondary: '#eeeef0',
    surface: '#ffffff',
    surfaceAlt: '#fafafa',
    surfaceHover: '#e8e8ec',
    inkPrimary: '#1c1c1e',
    inkSecondary: '#6c6c78',
    inkMuted: '#a0a0ab',
    inkLink: '#0a84ff',
    accent: '#0a84ff',
    accentHover: '#0070e0',
    accentSoft: 'rgba(10,132,255,.08)',
    accentGlow: 'rgba(10,132,255,.12)',
    success: '#34c759',
    successSoft: 'rgba(52,199,89,.12)',
    warning: '#ff9f0a',
    warningSoft: 'rgba(255,159,10,.12)',
    danger: '#ff3b30',
    dangerSoft: 'rgba(255,59,48,.10)',
    purple: '#af52de',
    purpleSoft: 'rgba(175,82,222,.10)',
    teal: '#5ac8fa',
    tealSoft: 'rgba(90,200,250,.12)',
    pink: '#ff2d92',
    pinkSoft: 'rgba(255,45,146,.10)',
    divider: '#e5e5ea',
    dividerHover: '#d1d1d6',
    dividerSoft: '#f0f0f2',
    aiMsg: '#f7f3ea',
    aiMsgStrong: '#efe9d8',
    userMsg: '#ebe7dd',
  },
  radius: {
    sm: 8,
    md: 14,
    lg: 18,
    xl: 24,
    full: 9999,
  },
  spacing: {
    space1: 4,
    space2: 8,
    space3: 14,
    space4: 18,
    space5: 28,
    space6: 36,
    space8: 56,
  },
  fontFamily: {
    sans: "'Inter','Noto Sans SC',system-ui,-apple-system,sans-serif",
    serif: "'Noto Serif SC','Iowan Old Style',serif",
    mono: "'SF Mono','JetBrains Mono',monospace",
  },
  easing: {
    easeOut: 'cubic-bezier(0,0,0.2,1)',
    easeSpring: 'cubic-bezier(0.34,1.56,0.64,1)',
  },
};

/**
 * Dark theme placeholder.
 * Not defined in Demo3.0. This interface serves as the contract.
 */
export const darkTheme: ThemeTokens = {
  ...lightTheme,
  // TODO: Define dark theme values when dark mode is implemented
};

export type Theme = 'light' | 'dark';
